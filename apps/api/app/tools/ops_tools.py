"""SQL-backed tools for the AI Ops Investigator.

These functions are intentionally deterministic and read-only.
They form the tool layer that LangGraph will orchestrate later.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from apps.api.app.database import engine


VALID_RELOAD_STATUSES = {
    "RUNNING",
    "SUCCESS",
    "FAILED",
    "CANCELLED",
    "SKIPPED",
}

VALID_LOG_LEVELS = {
    "DEBUG",
    "INFO",
    "WARN",
    "ERROR",
    "CRITICAL",
}


def _fetch_one(sql: str, params: dict[str, Any]) -> dict[str, Any] | None:
    """Execute a read-only query and return one row as a dictionary."""
    with engine.connect() as connection:
        row = connection.execute(text(sql), params).mappings().first()

    return dict(row) if row else None


def _fetch_all(sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    """Execute a read-only query and return all rows as dictionaries."""
    with engine.connect() as connection:
        rows = connection.execute(text(sql), params).mappings().all()

    return [dict(row) for row in rows]


def get_application(application_name: str) -> dict[str, Any] | None:
    """Return one application from its business name."""
    sql = """
        SELECT
            application_id,
            application_name,
            domain,
            business_owner,
            technical_owner,
            criticality,
            sla_time,
            sla_timezone,
            active
        FROM ops.applications
        WHERE lower(application_name) = lower(:application_name)
        LIMIT 1;
    """

    return _fetch_one(sql, {"application_name": application_name})


def get_reload_history(
    application_id: int,
    *,
    status: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Return the latest reload jobs for one application."""
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")

    if status is not None:
        status = status.upper()
        if status not in VALID_RELOAD_STATUSES:
            raise ValueError(
                f"status must be one of {sorted(VALID_RELOAD_STATUSES)}"
            )

    sql = """
        SELECT
            reload_id,
            application_id,
            started_at,
            ended_at,
            status,
            duration_seconds,
            rows_loaded,
            trigger_type,
            node_name,
            attempt_number,
            sla_breached
        FROM ops.reload_jobs
        WHERE application_id = :application_id
    """

    params: dict[str, Any] = {
        "application_id": application_id,
        "limit": limit,
    }

    if status is not None:
        sql += "\n          AND status = :status"
        params["status"] = status

    sql += """
        ORDER BY started_at DESC
        LIMIT :limit;
    """

    return _fetch_all(sql, params)


def get_reload_logs(
    reload_id: int,
    *,
    level: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Return chronological logs for one reload job."""
    if not 1 <= limit <= 1000:
        raise ValueError("limit must be between 1 and 1000")

    if level is not None:
        level = level.upper()
        if level not in VALID_LOG_LEVELS:
            raise ValueError(
                f"level must be one of {sorted(VALID_LOG_LEVELS)}"
            )

    sql = """
        SELECT
            log_id,
            reload_id,
            logged_at,
            level,
            component,
            message,
            error_code,
            data_source_id,
            correlation_id
        FROM ops.reload_logs
        WHERE reload_id = :reload_id
    """

    params: dict[str, Any] = {
        "reload_id": reload_id,
        "limit": limit,
    }

    if level is not None:
        sql += "\n          AND level = :level"
        params["level"] = level

    sql += """
        ORDER BY logged_at ASC, log_id ASC
        LIMIT :limit;
    """

    return _fetch_all(sql, params)


def get_incident(reload_id: int) -> dict[str, Any] | None:
    """Return the incident explicitly linked to one reload, when present."""
    sql = """
        SELECT
            incident_id,
            application_id,
            reload_id,
            opened_at,
            closed_at,
            severity,
            status,
            category,
            description,
            root_cause,
            detected_by
        FROM ops.incidents
        WHERE reload_id = :reload_id
        ORDER BY opened_at DESC
        LIMIT 1;
    """

    return _fetch_one(sql, {"reload_id": reload_id})


def get_jira_ticket(incident_id: int) -> dict[str, Any] | None:
    """Return the Jira ticket linked to one incident, when present."""
    sql = """
        SELECT
            ticket_id,
            jira_key,
            incident_id,
            created_at,
            updated_at,
            priority,
            status,
            assignee,
            summary,
            resolution
        FROM ops.jira_tickets
        WHERE incident_id = :incident_id
        ORDER BY created_at DESC
        LIMIT 1;
    """

    return _fetch_one(sql, {"incident_id": incident_id})


def check_dependencies(application_id: int) -> list[dict[str, Any]]:
    """Return the active data-source dependencies of one application."""
    sql = """
        SELECT
            d.dependency_id,
            d.application_id,
            d.data_source_id,
            d.dependency_type,
            d.critical_path,
            s.data_source_name,
            s.source_type,
            s.host_name,
            s.environment,
            s.criticality AS data_source_criticality,
            s.active AS data_source_active
        FROM ops.application_dependencies AS d
        JOIN ops.data_sources AS s
          ON s.data_source_id = d.data_source_id
        WHERE d.application_id = :application_id
          AND d.active = TRUE
        ORDER BY
            d.critical_path DESC,
            s.criticality DESC,
            s.data_source_name ASC;
    """

    return _fetch_all(sql, {"application_id": application_id})


TOOL_REGISTRY = {
    "get_application": get_application,
    "get_reload_history": get_reload_history,
    "get_reload_logs": get_reload_logs,
    "get_incident": get_incident,
    "get_jira_ticket": get_jira_ticket,
    "check_dependencies": check_dependencies,
}
