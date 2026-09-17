"""FastAPI routes for starting and streaming deterministic investigations."""

from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from apps.api.app.observability.live_stream import live_event_broker
from apps.api.app.services.investigation_service import run_investigation


router = APIRouter(
    prefix="/api/v1/investigations",
    tags=["investigations"],
)


class InvestigationRequest(BaseModel):
    prompt: str = Field(
        min_length=3,
        max_length=4000,
        examples=[
            "Pourquoi Sales_Analytics_033 a échoué lors de son dernier reload ?"
        ],
    )
    application_name: str | None = Field(
        default=None,
        max_length=255,
        examples=["Sales_Analytics_033"],
    )


class InvestigationStartResponse(BaseModel):
    run_id: UUID
    status: str
    stream_url: str
    state_url: str


def _encode_sse(event: dict) -> str:
    event_type = event.get("event_type") or "message"
    sequence_no = event.get("sequence_no")
    payload = json.dumps(
        event,
        ensure_ascii=False,
        default=str,
        separators=(",", ":"),
    )

    lines: list[str] = []
    if sequence_no is not None:
        lines.append(f"id: {sequence_no}")
    lines.append(f"event: {event_type}")
    lines.append(f"data: {payload}")
    return "\n".join(lines) + "\n\n"


@router.post(
    "",
    response_model=InvestigationStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_investigation(
    payload: InvestigationRequest,
) -> InvestigationStartResponse:
    run_id = uuid4()
    live_event_broker.create_run(run_id)

    asyncio.create_task(
        run_investigation(
            run_id=run_id,
            prompt=payload.prompt,
            application_name=payload.application_name,
        )
    )

    return InvestigationStartResponse(
        run_id=run_id,
        status="RUNNING",
        stream_url=f"/api/v1/investigations/{run_id}/stream",
        state_url=f"/api/v1/investigations/{run_id}",
    )


@router.get("/{run_id}")
async def get_investigation_state(run_id: UUID):
    snapshot = live_event_broker.snapshot(run_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Unknown run_id.")
    return snapshot


@router.get("/{run_id}/stream")
async def stream_investigation(
    run_id: UUID,
    request: Request,
) -> StreamingResponse:
    if not live_event_broker.exists(run_id):
        raise HTTPException(status_code=404, detail="Unknown run_id.")

    async def event_stream() -> AsyncIterator[str]:
        queue, buffered, already_done = live_event_broker.subscribe(run_id)

        try:
            for event in buffered:
                yield _encode_sse(event)

            if already_done:
                return

            while True:
                if await request.is_disconnected():
                    break

                if live_event_broker.is_done(run_id) and queue.empty():
                    break

                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                except TimeoutError:
                    # SSE comment = keep-alive; EventSource ignores it.
                    yield ": keep-alive\n\n"
                    continue

                yield _encode_sse(event)

        finally:
            live_event_broker.unsubscribe(run_id, queue)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
