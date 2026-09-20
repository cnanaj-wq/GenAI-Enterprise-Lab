"""FastAPI routes for starting and streaming deterministic investigations."""

from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import text

from apps.api.app.database import engine
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
        examples=["Pourquoi Sales_Analytics_033 a échoué lors de son dernier reload ?"],
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


@router.get("/history")
def list_investigation_history(
    limit: int = 50,
    status_filter: str | None = None,
):
    """Return persisted investigation traces from PostgreSQL observability."""
    safe_limit = max(1, min(limit, 200))

    sql = """
        SELECT
            t.trace_id,
            t.prompt,
            t.status,
            t.started_at,
            t.finished_at,
            t.duration_ms,
            t.provider,
            t.model,
            COALESCE(t.input_tokens, 0) AS input_tokens,
            COALESCE(t.output_tokens, 0) AS output_tokens,
            COALESCE(t.input_tokens, 0) + COALESCE(t.output_tokens, 0) AS total_tokens,
            COALESCE(t.estimated_cost_usd, 0) AS estimated_cost_usd,
            summary_event.event_data ->> 'application' AS application_name,
            CASE
                WHEN t.status = 'ERROR' THEN 'FAILED'
                WHEN EXISTS (
                    SELECT 1
                    FROM observability.events e
                    WHERE e.trace_id = t.trace_id
                      AND e.event_type = 'fallback_used'
                ) THEN 'FALLBACK'
                WHEN EXISTS (
                    SELECT 1
                    FROM observability.events e
                    WHERE e.trace_id = t.trace_id
                      AND e.event_type = 'mcp_retry_scheduled'
                ) THEN 'RETRY'
                ELSE 'OK'
            END AS resilience
        FROM observability.traces t
        LEFT JOIN LATERAL (
            SELECT event_data
            FROM observability.events e
            WHERE e.trace_id = t.trace_id
              AND e.event_type = 'investigation_summary'
            ORDER BY e.sequence_no DESC
            LIMIT 1
        ) AS summary_event ON TRUE
    """

    params = {"limit": safe_limit}

    if status_filter:
        sql += "\n WHERE t.status = :status_filter"
        params["status_filter"] = status_filter

    sql += """
        ORDER BY t.started_at DESC
        LIMIT :limit;
    """

    with engine.connect() as connection:
        rows = (
            connection.execute(
                text(sql),
                params,
            )
            .mappings()
            .all()
        )

    return {
        "count": len(rows),
        "items": [dict(row) for row in rows],
    }


def _load_trace_replay(trace_id: UUID) -> dict:
    with engine.connect() as connection:
        trace_row = (
            connection.execute(
                text(
                    """
                SELECT
                    trace_id,
                    conversation_id,
                    prompt,
                    status,
                    started_at,
                    finished_at,
                    duration_ms,
                    provider,
                    model,
                    prompt_version,
                    input_tokens,
                    output_tokens,
                    estimated_cost_usd,
                    error_type,
                    error_message
                FROM observability.traces
                WHERE trace_id = :trace_id;
                """
                ),
                {"trace_id": trace_id},
            )
            .mappings()
            .first()
        )

        if trace_row is None:
            raise HTTPException(status_code=404, detail="Unknown trace_id.")

        span_rows = (
            connection.execute(
                text(
                    """
                SELECT
                    span_id,
                    trace_id,
                    parent_span_id,
                    sequence_no,
                    span_type,
                    name,
                    status,
                    started_at,
                    finished_at,
                    duration_ms,
                    input_json,
                    output_json,
                    error_type,
                    error_message,
                    metadata_json
                FROM observability.spans
                WHERE trace_id = :trace_id
                ORDER BY sequence_no;
                """
                ),
                {"trace_id": trace_id},
            )
            .mappings()
            .all()
        )

        event_rows = (
            connection.execute(
                text(
                    """
                SELECT
                    trace_id,
                    span_id,
                    event_type,
                    occurred_at,
                    sequence_no,
                    event_data
                FROM observability.events
                WHERE trace_id = :trace_id
                ORDER BY sequence_no;
                """
                ),
                {"trace_id": trace_id},
            )
            .mappings()
            .all()
        )

    events = [dict(row) for row in event_rows]

    summary = next(
        (
            event["event_data"]
            for event in reversed(events)
            if event["event_type"] == "investigation_summary"
        ),
        None,
    )

    diagnosis = next(
        (
            event["event_data"]
            for event in reversed(events)
            if event["event_type"] == "diagnosis_ready"
        ),
        None,
    )

    breakdown = next(
        (
            event["event_data"]
            for event in reversed(events)
            if event["event_type"] == "execution_breakdown"
        ),
        None,
    )

    return {
        "replay": True,
        "trace": dict(trace_row),
        "spans": [dict(row) for row in span_rows],
        "events": events,
        "summary": summary,
        "diagnosis": diagnosis,
        "execution_breakdown": breakdown,
    }


@router.get("/traces/{trace_id}")
def get_trace_detail(trace_id: UUID):
    """Load a persisted trace and every span/event required to reconstruct it."""
    return _load_trace_replay(trace_id)


@router.get("/traces/{trace_id}/replay")
def replay_trace(trace_id: UUID):
    """Reconstruct a historical run without calling MCP, tools or the LLM again."""
    return _load_trace_replay(trace_id)


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
