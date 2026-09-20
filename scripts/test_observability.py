"""STEP 1.4B smoke test: persist a complete tool investigation as telemetry."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import text

from apps.api.app.database import engine
from apps.api.app.observability.telemetry import TelemetryRecorder
from apps.api.app.tools.ops_tools import (
    check_dependencies,
    get_application,
    get_incident,
    get_jira_ticket,
    get_reload_history,
    get_reload_logs,
)


def dump(title: str, value: Any) -> None:
    print(f"\n{'=' * 72}")
    print(title)
    print("=" * 72)
    print(json.dumps(value, indent=2, default=str, ensure_ascii=False))


def discover_candidate() -> dict[str, Any]:
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
        ORDER BY r.started_at DESC
        LIMIT 1;
    """

    with engine.connect() as connection:
        row = connection.execute(text(sql)).mappings().first()

    if row is None:
        raise RuntimeError("No FAILED reload found.")

    return dict(row)


def main() -> None:
    candidate = discover_candidate()

    recorder = TelemetryRecorder(
        event_callback=lambda event: print(
            f"[EVENT {event['sequence_no']:02d}] {event['event_type']:<14} {event['event_data']}"
        )
    )

    trace = recorder.start_trace(
        "Pourquoi l'application a-t-elle échoué lors de son dernier reload ?",
        provider="none",
        model="none",
        prompt_version="module1-step1.4b",
    )

    try:
        with recorder.span(
            trace.trace_id,
            "get_application",
            "TOOL",
            input_data={"application_name": candidate["application_name"]},
        ) as span:
            application = get_application(candidate["application_name"])
            recorder.finish_span(span, output_data=application)

        if application is None:
            raise RuntimeError("Application not found.")

        with recorder.span(
            trace.trace_id,
            "get_reload_history",
            "TOOL",
            input_data={
                "application_id": application["application_id"],
                "status": "FAILED",
                "limit": 5,
            },
        ) as span:
            history = get_reload_history(
                application["application_id"],
                status="FAILED",
                limit=5,
            )
            recorder.finish_span(
                span,
                output_data={"row_count": len(history), "rows": history},
            )

        reload_id = candidate["reload_id"]

        with recorder.span(
            trace.trace_id,
            "get_reload_logs",
            "TOOL",
            input_data={"reload_id": reload_id, "limit": 50},
        ) as span:
            logs = get_reload_logs(reload_id, limit=50)
            recorder.finish_span(
                span,
                output_data={"row_count": len(logs), "rows": logs},
            )

        with recorder.span(
            trace.trace_id,
            "get_incident",
            "TOOL",
            input_data={"reload_id": reload_id},
        ) as span:
            incident = get_incident(reload_id)
            recorder.finish_span(span, output_data=incident)

        jira = None
        if incident is not None:
            with recorder.span(
                trace.trace_id,
                "get_jira_ticket",
                "TOOL",
                input_data={"incident_id": incident["incident_id"]},
            ) as span:
                jira = get_jira_ticket(incident["incident_id"])
                recorder.finish_span(span, output_data=jira)

        with recorder.span(
            trace.trace_id,
            "check_dependencies",
            "TOOL",
            input_data={"application_id": application["application_id"]},
        ) as span:
            dependencies = check_dependencies(application["application_id"])
            recorder.finish_span(
                span,
                output_data={
                    "row_count": len(dependencies),
                    "rows": dependencies,
                },
            )

    except Exception as exc:
        recorder.finish_trace(trace, status="ERROR", error=exc)
        raise
    else:
        total_ms = recorder.finish_trace(trace, status="SUCCESS")

    with engine.connect() as connection:
        trace_row = (
            connection.execute(
                text(
                    """
                SELECT
                    trace_id,
                    prompt,
                    status,
                    started_at,
                    finished_at,
                    duration_ms,
                    provider,
                    model,
                    prompt_version
                FROM observability.traces
                WHERE trace_id = :trace_id;
                """
                ),
                {"trace_id": trace.trace_id},
            )
            .mappings()
            .one()
        )

        span_rows = (
            connection.execute(
                text(
                    """
                SELECT
                    sequence_no,
                    span_type,
                    name,
                    status,
                    duration_ms
                FROM observability.spans
                WHERE trace_id = :trace_id
                ORDER BY sequence_no;
                """
                ),
                {"trace_id": trace.trace_id},
            )
            .mappings()
            .all()
        )

        event_count = connection.execute(
            text(
                """
                SELECT count(*)
                FROM observability.events
                WHERE trace_id = :trace_id;
                """
            ),
            {"trace_id": trace.trace_id},
        ).scalar_one()

    dump("Persisted trace", dict(trace_row))
    dump("Persisted spans", [dict(row) for row in span_rows])

    print(f"\nEvents persisted : {event_count}")
    print(f"Trace duration   : {total_ms} ms")
    print(f"Trace ID         : {trace.trace_id}")
    print("\nSTEP 1.4B telemetry smoke test complete.")


if __name__ == "__main__":
    main()
