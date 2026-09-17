"""FastAPI gateway exposing MCP server status and metadata.

This does NOT replace the MCP endpoint on port 8001.
It gives humans / Swagger / Next.js a simple HTTP view through FastAPI :8000.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from mcp import Client


MCP_URL = "http://127.0.0.1:8001/mcp"

router = APIRouter(
    prefix="/api/v1/mcp",
    tags=["mcp"],
)


def _jsonable(value: Any) -> Any:
    """Convert MCP/Pydantic objects into plain JSON-compatible values."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]

    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return _jsonable(model_dump(mode="json"))

    return str(value)


@router.get("/status")
async def get_mcp_status() -> dict[str, Any]:
    """Check connectivity, protocol negotiation and exposed tool count."""
    try:
        async with Client(MCP_URL) as client:
            tools_result = await client.list_tools()

            return {
                "mcp": "healthy",
                "endpoint": MCP_URL,
                "protocol_version": client.protocol_version,
                "server_info": _jsonable(client.server_info),
                "tool_count": len(tools_result.tools),
                "capabilities": _jsonable(client.server_capabilities),
            }

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "mcp": "unhealthy",
                "endpoint": MCP_URL,
                "error_type": type(exc).__name__,
                "error": str(exc),
            },
        ) from exc


@router.get("/tools")
async def get_mcp_tools() -> dict[str, Any]:
    """List MCP tools and their input schemas."""
    try:
        async with Client(MCP_URL) as client:
            tools_result = await client.list_tools()

            tools = []
            for tool in tools_result.tools:
                tools.append(
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "input_schema": _jsonable(tool.input_schema),
                        "output_schema": _jsonable(
                            getattr(tool, "output_schema", None)
                        ),
                    }
                )

            return {
                "endpoint": MCP_URL,
                "protocol_version": client.protocol_version,
                "count": len(tools),
                "tools": tools,
            }

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "mcp": "unhealthy",
                "endpoint": MCP_URL,
                "error_type": type(exc).__name__,
                "error": str(exc),
            },
        ) from exc


@router.get("/manifest")
async def get_mcp_manifest() -> dict[str, Any]:
    """Read the MCP resource ops://manifest through the MCP client."""
    try:
        async with Client(MCP_URL) as client:
            resource = await client.read_resource("ops://manifest")

            return {
                "endpoint": MCP_URL,
                "protocol_version": client.protocol_version,
                "resource": _jsonable(resource),
            }

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "mcp": "unhealthy",
                "endpoint": MCP_URL,
                "error_type": type(exc).__name__,
                "error": str(exc),
            },
        ) from exc
