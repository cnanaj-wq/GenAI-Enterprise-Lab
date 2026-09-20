"""Run the AI Ops Investigator with LangGraph + MCP + OpenAI."""

from __future__ import annotations

from time import perf_counter
from typing import Any
from uuid import UUID

from apps.api.app.agents.ai_ops_graph import RunMetrics, ai_ops_graph
from apps.api.app.config import settings
from apps.api.app.mcp.client import (
    connect_mcp_resilient,
    mcp_circuit_breaker,
)
from apps.api.app.observability.live_stream import live_event_broker
from apps.api.app.observability.telemetry import TelemetryRecorder


def _percent(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(100.0 * part / total, 1)


async def run_investigation(
    *,
    run_id: UUID,
    prompt: str,
    application_name: str | None,
) -> None:
    recorder = TelemetryRecorder(
        event_callback=lambda event: live_event_broker.publish(run_id, event)
    )
    metrics = RunMetrics()

    trace = recorder.start_trace(
        prompt,
        provider="openai",
        model=settings.openai_model,
        prompt_version="ai-ops-diagnosis-v1-mcp",
    )

    final_state: dict[str, Any] = {}

    try:
        connect_span = recorder.start_span(
            trace.trace_id,
            "mcp:connect",
            "MCP",
            input_data={"endpoint": settings.mcp_url},
            metadata={"phase": "connection"},
        )
        connect_started = perf_counter()

        def on_connect_retry(payload: dict[str, Any]) -> None:
            recorder.record_event(
                trace.trace_id,
                "mcp_retry_scheduled",
                payload,
                span_id=connect_span.span_id,
            )

        def on_circuit_open(payload: dict[str, Any]) -> None:
            recorder.record_event(
                trace.trace_id,
                "mcp_circuit_opened",
                payload,
                span_id=connect_span.span_id,
            )

        try:
            connection = await connect_mcp_resilient(
                settings.mcp_url,
                on_retry=on_connect_retry,
                on_circuit_open=on_circuit_open,
            )
        except Exception as exc:
            connect_ms = round((perf_counter() - connect_started) * 1000)
            metrics.mcp_duration_ms += connect_ms
            recorder.finish_span(connect_span, status="ERROR", error=exc)
            raise

        connect_ms = round((perf_counter() - connect_started) * 1000)
        metrics.mcp_duration_ms += connect_ms
        mcp_client = connection.client
        protocol_version = str(mcp_client.protocol_version)

        recorder.finish_span(
            connect_span,
            output_data={
                "endpoint": settings.mcp_url,
                "protocol_version": protocol_version,
                "attempts": connection.attempts,
                "duration_ms": connect_ms,
                "circuit_state": mcp_circuit_breaker.state,
            },
        )

        recorder.record_event(
            trace.trace_id,
            "mcp_connected",
            {
                "endpoint": settings.mcp_url,
                "protocol_version": protocol_version,
                "server_info": str(mcp_client.server_info),
                "attempts": connection.attempts,
                "duration_ms": connect_ms,
                "circuit_state": mcp_circuit_breaker.state,
            },
            span_id=connect_span.span_id,
        )

        try:
            final_state = await ai_ops_graph.ainvoke(
                {
                    "prompt": prompt,
                    "application_name": application_name,
                },
                context={
                    "recorder": recorder,
                    "trace_id": trace.trace_id,
                    "metrics": metrics,
                    "mcp_client": mcp_client,
                    "mcp_endpoint": settings.mcp_url,
                    "mcp_protocol_version": protocol_version,
                },
            )
        finally:
            await connection.close()

        summary = {
            **final_state.get("summary", {}),
            "diagnosis": final_state.get("diagnosis"),
            "llm_usage": final_state.get("llm_usage"),
            "mcp_endpoint": settings.mcp_url,
        }

        recorder.record_event(
            trace.trace_id,
            "investigation_summary",
            summary,
        )

    except Exception as exc:
        recorder.record_event(
            trace.trace_id,
            "run_error",
            {
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "orchestrator": "LangGraph",
                "tool_interface": "MCP",
                "circuit_state": mcp_circuit_breaker.state,
            },
        )

        total_ms = recorder.finish_trace(
            trace,
            status="ERROR",
            error=exc,
        )

        unattributed_ms = max(
            total_ms - metrics.mcp_duration_ms - metrics.llm_duration_ms,
            0,
        )

        recorder.record_event(
            trace.trace_id,
            "execution_breakdown",
            {
                "total_ms": total_ms,
                "total_pct": 100.0,
                "mcp_duration_ms": metrics.mcp_duration_ms,
                "mcp_pct": _percent(metrics.mcp_duration_ms, total_ms),
                "llm_duration_ms": metrics.llm_duration_ms,
                "llm_pct": _percent(metrics.llm_duration_ms, total_ms),
                "unattributed_ms": unattributed_ms,
                "unattributed_pct": _percent(unattributed_ms, total_ms),
                "orchestrator": "LangGraph",
                "tool_interface": "MCP",
                "note": (
                    "MCP time is end-to-end round-trip time and therefore "
                    "includes transport + MCP server + remote tool execution. "
                    "Unattributed still includes LangGraph, telemetry, "
                    "database discovery and runtime overhead."
                ),
            },
        )

    else:
        llm_usage = final_state.get("llm_usage", {})

        total_ms = recorder.finish_trace(
            trace,
            status="SUCCESS",
            input_tokens=llm_usage.get("input_tokens"),
            output_tokens=llm_usage.get("output_tokens"),
            estimated_cost_usd=llm_usage.get("estimated_cost_usd"),
        )

        unattributed_ms = max(
            total_ms - metrics.mcp_duration_ms - metrics.llm_duration_ms,
            0,
        )

        recorder.record_event(
            trace.trace_id,
            "execution_breakdown",
            {
                "total_ms": total_ms,
                "total_pct": 100.0,
                "mcp_duration_ms": metrics.mcp_duration_ms,
                "mcp_pct": _percent(metrics.mcp_duration_ms, total_ms),
                "llm_duration_ms": metrics.llm_duration_ms,
                "llm_pct": _percent(metrics.llm_duration_ms, total_ms),
                "unattributed_ms": unattributed_ms,
                "unattributed_pct": _percent(unattributed_ms, total_ms),
                "orchestrator": "LangGraph",
                "tool_interface": "MCP",
                "note": (
                    "MCP time is end-to-end round-trip time and therefore "
                    "includes transport + MCP server + remote tool execution. "
                    "Unattributed still includes LangGraph, telemetry, "
                    "database discovery and runtime overhead."
                ),
            },
        )

    finally:
        live_event_broker.mark_done(run_id)
