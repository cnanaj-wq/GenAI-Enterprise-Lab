"""Run the AI Ops Investigator with LangGraph + MCP + OpenAI."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from mcp import Client

from apps.api.app.agents.ai_ops_graph import RunMetrics, ai_ops_graph
from apps.api.app.config import settings
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
        async with Client(settings.mcp_url) as mcp_client:
            protocol_version = str(mcp_client.protocol_version)

            recorder.record_event(
                trace.trace_id,
                "mcp_connected",
                {
                    "endpoint": settings.mcp_url,
                    "protocol_version": protocol_version,
                    "server_info": str(mcp_client.server_info),
                },
            )

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
        total_ms = recorder.finish_trace(
            trace,
            status="ERROR",
            error=exc,
        )

        unattributed_ms = max(
            total_ms
            - metrics.mcp_duration_ms
            - metrics.llm_duration_ms,
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

        live_event_broker.publish(
            run_id,
            {
                "trace_id": str(trace.trace_id),
                "span_id": None,
                "event_type": "run_error",
                "occurred_at": None,
                "sequence_no": None,
                "event_data": {
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    "orchestrator": "LangGraph",
                    "tool_interface": "MCP",
                },
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
            total_ms
            - metrics.mcp_duration_ms
            - metrics.llm_duration_ms,
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
