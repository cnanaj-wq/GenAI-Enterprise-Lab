"""Trace / Span / Event persistence for the GenAI Enterprise Lab."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from time import perf_counter
from typing import Any, Callable
from uuid import UUID, uuid4

from sqlalchemy import text

from apps.api.app.database import engine

EventCallback = Callable[[dict[str, Any]], None]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    return str(value)


@dataclass
class SpanHandle:
    span_id: UUID
    trace_id: UUID
    name: str
    span_type: str
    sequence_no: int
    started_at: datetime
    _started_perf: float = field(repr=False)


@dataclass
class TraceHandle:
    trace_id: UUID
    prompt: str
    started_at: datetime
    _started_perf: float = field(repr=False)


class TelemetryRecorder:
    VALID_SPAN_TYPES = {
        "NODE",
        "TOOL",
        "MCP",
        "LLM",
        "DATABASE",
        "EVALUATION",
        "OTHER",
    }

    def __init__(self, event_callback: EventCallback | None = None) -> None:
        self.event_callback = event_callback
        self._span_sequence: dict[UUID, int] = {}
        self._event_sequence: dict[UUID, int] = {}

    def _next_span_sequence(self, trace_id: UUID) -> int:
        value = self._span_sequence.get(trace_id, 0) + 1
        self._span_sequence[trace_id] = value
        return value

    def _next_event_sequence(self, trace_id: UUID) -> int:
        value = self._event_sequence.get(trace_id, 0) + 1
        self._event_sequence[trace_id] = value
        return value

    def start_trace(
        self,
        prompt: str,
        *,
        conversation_id: UUID | None = None,
        provider: str | None = None,
        model: str | None = None,
        prompt_version: str | None = None,
    ) -> TraceHandle:
        trace_id = uuid4()
        started_at = _utc_now()

        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO observability.traces (
                        trace_id,
                        conversation_id,
                        prompt,
                        status,
                        started_at,
                        provider,
                        model,
                        prompt_version
                    )
                    VALUES (
                        :trace_id,
                        :conversation_id,
                        :prompt,
                        'RUNNING',
                        :started_at,
                        :provider,
                        :model,
                        :prompt_version
                    );
                    """
                ),
                {
                    "trace_id": trace_id,
                    "conversation_id": conversation_id,
                    "prompt": prompt,
                    "started_at": started_at,
                    "provider": provider,
                    "model": model,
                    "prompt_version": prompt_version,
                },
            )

        handle = TraceHandle(
            trace_id=trace_id,
            prompt=prompt,
            started_at=started_at,
            _started_perf=perf_counter(),
        )

        self.record_event(
            trace_id,
            "trace_started",
            {
                "prompt": prompt,
                "provider": provider,
                "model": model,
                "prompt_version": prompt_version,
            },
        )

        return handle

    def finish_trace(
        self,
        trace: TraceHandle,
        *,
        status: str = "SUCCESS",
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        estimated_cost_usd: float | None = None,
        error: BaseException | None = None,
    ) -> int:
        finished_at = _utc_now()
        duration_ms = round((perf_counter() - trace._started_perf) * 1000)

        error_type = type(error).__name__ if error else None
        error_message = str(error) if error else None

        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    UPDATE observability.traces
                    SET
                        status = :status,
                        finished_at = :finished_at,
                        duration_ms = :duration_ms,
                        input_tokens = :input_tokens,
                        output_tokens = :output_tokens,
                        estimated_cost_usd = :estimated_cost_usd,
                        error_type = :error_type,
                        error_message = :error_message
                    WHERE trace_id = :trace_id;
                    """
                ),
                {
                    "trace_id": trace.trace_id,
                    "status": status,
                    "finished_at": finished_at,
                    "duration_ms": duration_ms,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "estimated_cost_usd": estimated_cost_usd,
                    "error_type": error_type,
                    "error_message": error_message,
                },
            )

        self.record_event(
            trace.trace_id,
            "trace_finished",
            {
                "status": status,
                "duration_ms": duration_ms,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "estimated_cost_usd": estimated_cost_usd,
                "error_type": error_type,
                "error_message": error_message,
            },
        )

        return duration_ms

    def start_span(
        self,
        trace_id: UUID,
        name: str,
        span_type: str,
        *,
        parent_span_id: UUID | None = None,
        input_data: Any = None,
        metadata: dict[str, Any] | None = None,
    ) -> SpanHandle:
        import json

        span_type = span_type.upper()
        if span_type not in self.VALID_SPAN_TYPES:
            raise ValueError(f"span_type must be one of {sorted(self.VALID_SPAN_TYPES)}")

        span_id = uuid4()
        sequence_no = self._next_span_sequence(trace_id)
        started_at = _utc_now()

        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO observability.spans (
                        span_id,
                        trace_id,
                        parent_span_id,
                        sequence_no,
                        span_type,
                        name,
                        status,
                        started_at,
                        input_json,
                        metadata_json
                    )
                    VALUES (
                        :span_id,
                        :trace_id,
                        :parent_span_id,
                        :sequence_no,
                        :span_type,
                        :name,
                        'RUNNING',
                        :started_at,
                        CAST(:input_json AS jsonb),
                        CAST(:metadata_json AS jsonb)
                    );
                    """
                ),
                {
                    "span_id": span_id,
                    "trace_id": trace_id,
                    "parent_span_id": parent_span_id,
                    "sequence_no": sequence_no,
                    "span_type": span_type,
                    "name": name,
                    "started_at": started_at,
                    "input_json": json.dumps(_json_safe(input_data)),
                    "metadata_json": json.dumps(_json_safe(metadata)),
                },
            )

        handle = SpanHandle(
            span_id=span_id,
            trace_id=trace_id,
            name=name,
            span_type=span_type,
            sequence_no=sequence_no,
            started_at=started_at,
            _started_perf=perf_counter(),
        )

        self.record_event(
            trace_id,
            "span_started",
            {
                "span_id": span_id,
                "parent_span_id": parent_span_id,
                "name": name,
                "span_type": span_type,
                "sequence_no": sequence_no,
            },
            span_id=span_id,
        )

        return handle

    def finish_span(
        self,
        span: SpanHandle,
        *,
        status: str = "SUCCESS",
        output_data: Any = None,
        error: BaseException | None = None,
    ) -> int:
        import json

        finished_at = _utc_now()
        duration_ms = round((perf_counter() - span._started_perf) * 1000)
        error_type = type(error).__name__ if error else None
        error_message = str(error) if error else None

        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    UPDATE observability.spans
                    SET
                        status = :status,
                        finished_at = :finished_at,
                        duration_ms = :duration_ms,
                        output_json = CAST(:output_json AS jsonb),
                        error_type = :error_type,
                        error_message = :error_message
                    WHERE span_id = :span_id;
                    """
                ),
                {
                    "span_id": span.span_id,
                    "status": status,
                    "finished_at": finished_at,
                    "duration_ms": duration_ms,
                    "output_json": json.dumps(_json_safe(output_data)),
                    "error_type": error_type,
                    "error_message": error_message,
                },
            )

        self.record_event(
            span.trace_id,
            "span_finished",
            {
                "span_id": span.span_id,
                "name": span.name,
                "span_type": span.span_type,
                "status": status,
                "duration_ms": duration_ms,
                "error_type": error_type,
                "error_message": error_message,
            },
            span_id=span.span_id,
        )

        return duration_ms

    def record_event(
        self,
        trace_id: UUID,
        event_type: str,
        event_data: Any = None,
        *,
        span_id: UUID | None = None,
    ) -> dict[str, Any]:
        import json

        occurred_at = _utc_now()
        sequence_no = self._next_event_sequence(trace_id)
        safe_data = _json_safe(event_data)

        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO observability.events (
                        trace_id,
                        span_id,
                        event_type,
                        occurred_at,
                        sequence_no,
                        event_data
                    )
                    VALUES (
                        :trace_id,
                        :span_id,
                        :event_type,
                        :occurred_at,
                        :sequence_no,
                        CAST(:event_data AS jsonb)
                    );
                    """
                ),
                {
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "event_type": event_type,
                    "occurred_at": occurred_at,
                    "sequence_no": sequence_no,
                    "event_data": json.dumps(safe_data),
                },
            )

        payload = {
            "trace_id": str(trace_id),
            "span_id": str(span_id) if span_id else None,
            "event_type": event_type,
            "occurred_at": occurred_at.isoformat(),
            "sequence_no": sequence_no,
            "event_data": safe_data,
        }

        if self.event_callback is not None:
            self.event_callback(payload)

        return payload
