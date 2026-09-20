"""LangGraph orchestration using MCP as the enterprise tool interface."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Literal
from uuid import UUID

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from mcp import Client
from sqlalchemy import text
from typing_extensions import NotRequired, TypedDict

from apps.api.app.config import settings
from apps.api.app.database import engine
from apps.api.app.llm.openai_provider import generate_diagnosis
from apps.api.app.mcp.client import (
    MCPCircuitOpenError,
    call_mcp_tool_resilient,
    mcp_circuit_breaker,
)
from apps.api.app.observability.telemetry import SpanHandle, TelemetryRecorder


class InvestigatorState(TypedDict):
    prompt: str
    application_name: str | None

    candidate: NotRequired[dict[str, Any]]
    application: NotRequired[dict[str, Any]]
    reload_history: NotRequired[list[dict[str, Any]]]
    reload_logs: NotRequired[list[dict[str, Any]]]
    incident: NotRequired[dict[str, Any] | None]
    jira_ticket: NotRequired[dict[str, Any] | None]
    dependencies: NotRequired[list[dict[str, Any]]]
    root_error_codes: NotRequired[list[str]]
    summary: NotRequired[dict[str, Any]]
    diagnosis: NotRequired[str]
    llm_usage: NotRequired[dict[str, Any]]


@dataclass
class RunMetrics:
    mcp_duration_ms: int = 0
    llm_duration_ms: int = 0


class RunContext(TypedDict):
    recorder: TelemetryRecorder
    trace_id: UUID
    metrics: RunMetrics
    mcp_client: Client
    mcp_endpoint: str
    mcp_protocol_version: str


def _recorder(runtime: Runtime[RunContext]) -> TelemetryRecorder:
    return runtime.context["recorder"]


def _trace_id(runtime: Runtime[RunContext]) -> UUID:
    return runtime.context["trace_id"]


def _metrics(runtime: Runtime[RunContext]) -> RunMetrics:
    return runtime.context["metrics"]


async def _execute_node(
    runtime: Runtime[RunContext],
    *,
    name: str,
    input_data: Any,
    body,
) -> dict[str, Any]:
    recorder = _recorder(runtime)
    trace_id = _trace_id(runtime)

    node_span = recorder.start_span(
        trace_id,
        name,
        "NODE",
        input_data=input_data,
        metadata={"orchestrator": "langgraph"},
    )

    try:
        output = await body(node_span)
    except Exception as exc:
        recorder.finish_span(node_span, status="ERROR", error=exc)
        raise
    else:
        recorder.finish_span(node_span, output_data=output)
        return output


async def _execute_mcp_tool(
    runtime: Runtime[RunContext],
    *,
    parent_span: SpanHandle,
    name: str,
    arguments: dict[str, Any],
) -> Any:
    recorder = _recorder(runtime)
    trace_id = _trace_id(runtime)

    mcp_span = recorder.start_span(
        trace_id,
        f"mcp:{name}",
        "MCP",
        parent_span_id=parent_span.span_id,
        input_data={
            "tool": name,
            "arguments": arguments,
        },
        metadata={
            "endpoint": runtime.context["mcp_endpoint"],
            "protocol_version": runtime.context["mcp_protocol_version"],
        },
    )

    started = perf_counter()

    def on_retry(payload: dict[str, Any]) -> None:
        recorder.record_event(
            trace_id,
            "mcp_retry_scheduled",
            payload,
            span_id=mcp_span.span_id,
        )

    try:
        call = await call_mcp_tool_resilient(
            runtime.context["mcp_client"],
            name,
            arguments,
            on_retry=on_retry,
        )
        result = call.value
        attempts = call.attempts
    except MCPCircuitOpenError as exc:
        duration_ms = round((perf_counter() - started) * 1000)
        _metrics(runtime).mcp_duration_ms += duration_ms

        recorder.record_event(
            trace_id,
            "mcp_circuit_opened",
            {
                "tool": name,
                "circuit_state": mcp_circuit_breaker.state,
                "consecutive_failures": mcp_circuit_breaker.consecutive_failures,
                "cooldown_seconds": settings.mcp_circuit_cooldown_seconds,
                "error_message": str(exc),
            },
            span_id=mcp_span.span_id,
        )

        recorder.finish_span(mcp_span, status="ERROR", error=exc)
        raise

    except Exception as exc:
        duration_ms = round((perf_counter() - started) * 1000)
        _metrics(runtime).mcp_duration_ms += duration_ms
        recorder.finish_span(mcp_span, status="ERROR", error=exc)
        recorder.record_event(
            trace_id,
            "mcp_measurement",
            {
                "tool": name,
                "endpoint": runtime.context["mcp_endpoint"],
                "protocol_version": runtime.context["mcp_protocol_version"],
                "duration_ms": duration_ms,
                "status": "ERROR",
                "circuit_state": mcp_circuit_breaker.state,
            },
            span_id=mcp_span.span_id,
        )
        raise

    duration_ms = round((perf_counter() - started) * 1000)
    _metrics(runtime).mcp_duration_ms += duration_ms

    stored_result: Any
    if isinstance(result, list):
        stored_result = {"row_count": len(result), "rows": result}
    else:
        stored_result = result

    recorder.finish_span(
        mcp_span,
        output_data={
            "tool_result": stored_result,
            "mcp_round_trip_ms": duration_ms,
            "attempts": attempts,
            "circuit_state": mcp_circuit_breaker.state,
        },
    )

    recorder.record_event(
        trace_id,
        "mcp_measurement",
        {
            "tool": name,
            "endpoint": runtime.context["mcp_endpoint"],
            "protocol_version": runtime.context["mcp_protocol_version"],
            "duration_ms": duration_ms,
            "attempts": attempts,
            "status": "SUCCESS",
            "circuit_state": mcp_circuit_breaker.state,
        },
        span_id=mcp_span.span_id,
    )

    return result


def _discover_failed_reload(
    application_name: str | None,
) -> dict[str, Any]:
    sql = """
        SELECT
            a.application_name,
            r.application_id,
            r.reload_id,
            r.started_at
        FROM ops.reload_jobs AS r
        JOIN ops.applications AS a
          ON a.application_id = r.application_id
        WHERE r.status = 'FAILED'
    """

    params: dict[str, Any] = {}

    if application_name:
        sql += "\n  AND lower(a.application_name) = lower(:application_name)"
        params["application_name"] = application_name

    sql += """
        ORDER BY r.started_at DESC
        LIMIT 1;
    """

    with engine.connect() as connection:
        row = connection.execute(text(sql), params).mappings().first()

    if row is None:
        if application_name:
            raise RuntimeError(f"No FAILED reload found for application {application_name!r}.")
        raise RuntimeError("No FAILED reload found in the dataset.")

    return dict(row)


async def select_candidate(
    state: InvestigatorState,
    runtime: Runtime[RunContext],
) -> dict[str, Any]:
    async def body(node_span: SpanHandle) -> dict[str, Any]:
        recorder = _recorder(runtime)
        trace_id = _trace_id(runtime)

        db_span = recorder.start_span(
            trace_id,
            "discover_failed_reload",
            "DATABASE",
            parent_span_id=node_span.span_id,
            input_data={"application_name": state.get("application_name")},
        )

        started = perf_counter()

        try:
            candidate = await asyncio.to_thread(
                _discover_failed_reload,
                state.get("application_name"),
            )
        except Exception as exc:
            recorder.finish_span(db_span, status="ERROR", error=exc)
            raise

        db_ms = round((perf_counter() - started) * 1000)
        recorder.finish_span(
            db_span,
            output_data={
                "candidate": candidate,
                "database_duration_ms": db_ms,
            },
        )

        recorder.record_event(
            trace_id,
            "candidate_selected",
            candidate,
            span_id=node_span.span_id,
        )

        return {"candidate": candidate}

    return await _execute_node(
        runtime,
        name="select_candidate",
        input_data={"application_name": state.get("application_name")},
        body=body,
    )


async def load_application(
    state: InvestigatorState,
    runtime: Runtime[RunContext],
) -> dict[str, Any]:
    candidate = state["candidate"]

    async def body(node_span: SpanHandle) -> dict[str, Any]:
        application = await _execute_mcp_tool(
            runtime,
            parent_span=node_span,
            name="get_application",
            arguments={"application_name": candidate["application_name"]},
        )

        if application is None:
            raise RuntimeError("Application lookup returned no row.")

        return {"application": application}

    return await _execute_node(
        runtime,
        name="load_application",
        input_data={"candidate": candidate},
        body=body,
    )


async def inspect_reload_history(
    state: InvestigatorState,
    runtime: Runtime[RunContext],
) -> dict[str, Any]:
    application = state["application"]

    async def body(node_span: SpanHandle) -> dict[str, Any]:
        history = await _execute_mcp_tool(
            runtime,
            parent_span=node_span,
            name="get_reload_history",
            arguments={
                "application_id": application["application_id"],
                "status": "FAILED",
                "limit": 5,
            },
        )
        return {"reload_history": history}

    return await _execute_node(
        runtime,
        name="inspect_reload_history",
        input_data={"application_id": application["application_id"]},
        body=body,
    )


async def inspect_reload_logs(
    state: InvestigatorState,
    runtime: Runtime[RunContext],
) -> dict[str, Any]:
    reload_id = state["candidate"]["reload_id"]

    async def body(node_span: SpanHandle) -> dict[str, Any]:
        logs = await _execute_mcp_tool(
            runtime,
            parent_span=node_span,
            name="get_reload_logs",
            arguments={"reload_id": reload_id, "limit": 50},
        )

        root_error_codes = [
            row["error_code"]
            for row in logs
            if row.get("error_code") and row["error_code"] != "RELOAD_ABORTED"
        ]

        return {
            "reload_logs": logs,
            "root_error_codes": root_error_codes,
        }

    return await _execute_node(
        runtime,
        name="inspect_reload_logs",
        input_data={"reload_id": reload_id},
        body=body,
    )


async def lookup_incident(
    state: InvestigatorState,
    runtime: Runtime[RunContext],
) -> dict[str, Any]:
    reload_id = state["candidate"]["reload_id"]

    async def body(node_span: SpanHandle) -> dict[str, Any]:
        incident = await _execute_mcp_tool(
            runtime,
            parent_span=node_span,
            name="get_incident",
            arguments={"reload_id": reload_id},
        )

        selected = "lookup_jira" if incident is not None else "inspect_dependencies"

        _recorder(runtime).record_event(
            _trace_id(runtime),
            "route_decision",
            {
                "from": "lookup_incident",
                "condition": "incident_present",
                "selected": selected,
            },
            span_id=node_span.span_id,
        )

        return {"incident": incident}

    return await _execute_node(
        runtime,
        name="lookup_incident",
        input_data={"reload_id": reload_id},
        body=body,
    )


def route_after_incident(
    state: InvestigatorState,
) -> Literal["lookup_jira", "inspect_dependencies"]:
    if state.get("incident") is not None:
        return "lookup_jira"
    return "inspect_dependencies"


async def lookup_jira(
    state: InvestigatorState,
    runtime: Runtime[RunContext],
) -> dict[str, Any]:
    incident = state["incident"]
    if incident is None:
        return {"jira_ticket": None}

    async def body(node_span: SpanHandle) -> dict[str, Any]:
        jira = await _execute_mcp_tool(
            runtime,
            parent_span=node_span,
            name="get_jira_ticket",
            arguments={"incident_id": incident["incident_id"]},
        )
        return {"jira_ticket": jira}

    return await _execute_node(
        runtime,
        name="lookup_jira",
        input_data={"incident_id": incident["incident_id"]},
        body=body,
    )


async def inspect_dependencies(
    state: InvestigatorState,
    runtime: Runtime[RunContext],
) -> dict[str, Any]:
    application = state["application"]

    async def body(node_span: SpanHandle) -> dict[str, Any]:
        dependencies = await _execute_mcp_tool(
            runtime,
            parent_span=node_span,
            name="check_dependencies",
            arguments={"application_id": application["application_id"]},
        )
        return {"dependencies": dependencies}

    return await _execute_node(
        runtime,
        name="inspect_dependencies",
        input_data={"application_id": application["application_id"]},
        body=body,
    )


async def build_summary(
    state: InvestigatorState,
    runtime: Runtime[RunContext],
) -> dict[str, Any]:
    async def body(_node_span: SpanHandle) -> dict[str, Any]:
        incident = state.get("incident")
        jira = state.get("jira_ticket")

        return {
            "summary": {
                "application": state["application"]["application_name"],
                "reload_id": state["candidate"]["reload_id"],
                "failed_history_count": len(state.get("reload_history", [])),
                "root_error_codes": state.get("root_error_codes", []),
                "incident_id": incident["incident_id"] if incident else None,
                "jira_key": jira["jira_key"] if jira else None,
                "dependency_count": len(state.get("dependencies", [])),
                "orchestrator": "LangGraph",
                "tool_interface": "MCP",
            }
        }

    return await _execute_node(
        runtime,
        name="build_summary",
        input_data={"prompt": state["prompt"]},
        body=body,
    )


def _llm_evidence(state: InvestigatorState) -> dict[str, Any]:
    relevant_logs = [
        {
            "logged_at": row["logged_at"],
            "level": row["level"],
            "component": row["component"],
            "message": row["message"],
            "error_code": row["error_code"],
            "data_source_id": row["data_source_id"],
        }
        for row in state.get("reload_logs", [])
        if row["level"] in {"WARN", "ERROR", "CRITICAL"} or row.get("error_code")
    ]

    return {
        "application": state.get("application"),
        "reload": state.get("candidate"),
        "root_error_codes": state.get("root_error_codes", []),
        "relevant_logs": relevant_logs,
        "incident": state.get("incident"),
        "jira_ticket": state.get("jira_ticket"),
        "dependencies": state.get("dependencies", []),
        "deterministic_summary": state.get("summary"),
    }


def _deterministic_fallback_diagnosis(state: InvestigatorState) -> str:
    """Generate a bounded diagnosis when the LLM is unavailable."""
    errors = state.get("root_error_codes", [])
    incident = state.get("incident")
    jira = state.get("jira_ticket")
    application = state.get("application", {})
    candidate = state.get("candidate", {})

    primary_error = errors[0] if errors else "CAUSE_NON_DETERMINEE"

    incident_text = (
        f"Incident {incident.get('incident_id')} — "
        f"{incident.get('root_cause', 'cause documentée indisponible')}"
        if incident
        else "Aucun incident lié n'a été trouvé."
    )

    jira_text = (
        f"Ticket {jira.get('jira_key')} ({jira.get('status', 'statut inconnu')})."
        if jira
        else "Aucun ticket Jira lié n'a été trouvé."
    )

    return (
        "1. Diagnostic\\n"
        f"Mode dégradé déterministe : le reload "
        f"{candidate.get('reload_id', 'inconnu')} de "
        f"{application.get('application_name', 'l’application')} a échoué. "
        f"Erreur principale observée : {primary_error}.\\n\\n"
        "2. Preuves\\n"
        f"- Codes d'erreur : {', '.join(errors) if errors else 'aucun code spécifique'}\\n"
        f"- {incident_text}\\n"
        f"- {jira_text}\\n\\n"
        "3. Impact\\n"
        "Le diagnostic est limité aux preuves structurées collectées par les tools.\\n\\n"
        "4. Action corrective\\n"
        "Traiter la cause documentée dans les logs/incident, puis relancer le reload "
        "et vérifier son statut.\\n\\n"
        "5. Confiance\\n"
        "Moyenne — réponse de secours générée sans LLM."
    )


async def generate_llm_diagnosis(
    state: InvestigatorState,
    runtime: Runtime[RunContext],
) -> dict[str, Any]:
    async def body(node_span: SpanHandle) -> dict[str, Any]:
        recorder = _recorder(runtime)
        trace_id = _trace_id(runtime)
        evidence = _llm_evidence(state)

        llm_span = recorder.start_span(
            trace_id,
            "generate_diagnosis",
            "LLM",
            parent_span_id=node_span.span_id,
            input_data={
                "prompt": state["prompt"],
                "evidence": evidence,
            },
            metadata={
                "provider": "openai",
                "purpose": "grounded_ops_diagnosis",
            },
        )

        started = perf_counter()

        try:
            result = await asyncio.to_thread(
                generate_diagnosis,
                user_prompt=state["prompt"],
                evidence=evidence,
            )
        except Exception as exc:
            duration_ms = round((perf_counter() - started) * 1000)
            _metrics(runtime).llm_duration_ms += duration_ms
            recorder.finish_span(llm_span, status="ERROR", error=exc)

            fallback = _deterministic_fallback_diagnosis(state)
            fallback_usage = {
                "provider": "fallback",
                "model": "deterministic",
                "response_id": None,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "estimated_cost_usd": 0.0,
                "duration_ms": duration_ms,
                "fallback": True,
            }

            recorder.record_event(
                trace_id,
                "fallback_used",
                {
                    "component": "llm",
                    "reason": type(exc).__name__,
                    "error_message": str(exc),
                    "strategy": "deterministic_diagnosis",
                },
                span_id=llm_span.span_id,
            )

            recorder.record_event(
                trace_id,
                "diagnosis_ready",
                {
                    "diagnosis": fallback,
                    **fallback_usage,
                },
                span_id=llm_span.span_id,
            )

            return {
                "diagnosis": fallback,
                "llm_usage": fallback_usage,
            }

        duration_ms = round((perf_counter() - started) * 1000)
        _metrics(runtime).llm_duration_ms += duration_ms

        usage = {
            "provider": result.provider,
            "model": result.model,
            "response_id": result.response_id,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "total_tokens": result.total_tokens,
            "estimated_cost_usd": result.estimated_cost_usd,
            "duration_ms": duration_ms,
        }

        recorder.finish_span(
            llm_span,
            output_data={
                "diagnosis": result.text,
                "usage": usage,
            },
        )

        recorder.record_event(
            trace_id,
            "llm_measurement",
            usage,
            span_id=llm_span.span_id,
        )

        recorder.record_event(
            trace_id,
            "diagnosis_ready",
            {
                "diagnosis": result.text,
                **usage,
            },
            span_id=llm_span.span_id,
        )

        return {
            "diagnosis": result.text,
            "llm_usage": usage,
        }

    return await _execute_node(
        runtime,
        name="generate_llm_diagnosis",
        input_data={
            "prompt": state["prompt"],
            "summary": state.get("summary"),
        },
        body=body,
    )


def build_ai_ops_graph():
    builder = StateGraph(
        InvestigatorState,
        context_schema=RunContext,
    )

    builder.add_node("select_candidate", select_candidate)
    builder.add_node("load_application", load_application)
    builder.add_node("inspect_reload_history", inspect_reload_history)
    builder.add_node("inspect_reload_logs", inspect_reload_logs)
    builder.add_node("lookup_incident", lookup_incident)
    builder.add_node("lookup_jira", lookup_jira)
    builder.add_node("inspect_dependencies", inspect_dependencies)
    builder.add_node("build_summary", build_summary)
    builder.add_node("generate_llm_diagnosis", generate_llm_diagnosis)

    builder.add_edge(START, "select_candidate")
    builder.add_edge("select_candidate", "load_application")
    builder.add_edge("load_application", "inspect_reload_history")
    builder.add_edge("inspect_reload_history", "inspect_reload_logs")
    builder.add_edge("inspect_reload_logs", "lookup_incident")

    builder.add_conditional_edges(
        "lookup_incident",
        route_after_incident,
        ["lookup_jira", "inspect_dependencies"],
    )

    builder.add_edge("lookup_jira", "inspect_dependencies")
    builder.add_edge("inspect_dependencies", "build_summary")
    builder.add_edge("build_summary", "generate_llm_diagnosis")
    builder.add_edge("generate_llm_diagnosis", END)

    return builder.compile()


ai_ops_graph = build_ai_ops_graph()
