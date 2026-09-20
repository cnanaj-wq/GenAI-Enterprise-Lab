"""MCP v2 server exposing the AI Ops Investigator tools."""

from __future__ import annotations

import os
from datetime import date, datetime, time
from typing import Any
from uuid import UUID

from mcp.server import MCPServer

from apps.api.app.tools.ops_tools import (
    check_dependencies as check_dependencies_local,
)
from apps.api.app.tools.ops_tools import (
    get_application as get_application_local,
)
from apps.api.app.tools.ops_tools import (
    get_incident as get_incident_local,
)
from apps.api.app.tools.ops_tools import (
    get_jira_ticket as get_jira_ticket_local,
)
from apps.api.app.tools.ops_tools import (
    get_reload_history as get_reload_history_local,
)
from apps.api.app.tools.ops_tools import (
    get_reload_logs as get_reload_logs_local,
)

mcp = MCPServer(
    "GenAI Enterprise Lab - AI Ops Tools",
    instructions=(
        "Read-only operational tools for investigating application reload "
        "failures. Use PostgreSQL evidence only; do not invent data."
    ),
)


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    return str(value)


@mcp.tool()
def get_application(application_name: str) -> dict[str, Any] | None:
    """Resolve an application name to its id, ownership, criticality and SLA."""
    return _json_safe(get_application_local(application_name))


@mcp.tool()
def get_reload_history(
    application_id: int,
    status: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Return recent reload jobs for one application."""
    return _json_safe(
        get_reload_history_local(
            application_id,
            status=status,
            limit=limit,
        )
    )


@mcp.tool()
def get_reload_logs(
    reload_id: int,
    level: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Return chronological reload logs and root-cause evidence."""
    return _json_safe(
        get_reload_logs_local(
            reload_id,
            level=level,
            limit=limit,
        )
    )


@mcp.tool()
def get_incident(reload_id: int) -> dict[str, Any] | None:
    """Return the incident explicitly linked to a reload, if any."""
    return _json_safe(get_incident_local(reload_id))


@mcp.tool()
def get_jira_ticket(incident_id: int) -> dict[str, Any] | None:
    """Return the Jira ticket linked to an incident, if any."""
    return _json_safe(get_jira_ticket_local(incident_id))


@mcp.tool()
def check_dependencies(application_id: int) -> list[dict[str, Any]]:
    """Return active data-source dependencies for an application."""
    return _json_safe(check_dependencies_local(application_id))


@mcp.resource("ops://manifest")
def ops_manifest() -> dict[str, Any]:
    """Describe this read-only MCP server."""
    return {
        "name": "GenAI Enterprise Lab - AI Ops Tools",
        "mode": "read-only",
        "database_schema": "ops",
        "tools": [
            "get_application",
            "get_reload_history",
            "get_reload_logs",
            "get_incident",
            "get_jira_ticket",
            "check_dependencies",
        ],
        "transport_default": "streamable-http",
        "endpoint_default": "http://127.0.0.1:8001/mcp",
    }


def main() -> None:
    transport = os.getenv("MCP_TRANSPORT", "streamable-http").strip().lower()

    if transport == "stdio":
        mcp.run(transport="stdio")
        return

    if transport != "streamable-http":
        raise ValueError("MCP_TRANSPORT must be 'streamable-http' or 'stdio'.")

    host = os.getenv("MCP_HOST", "127.0.0.1")
    port = int(os.getenv("MCP_PORT", "8001"))

    mcp.run(
        transport="streamable-http",
        host=host,
        port=port,
        streamable_http_path="/mcp",
    )


if __name__ == "__main__":
    main()
