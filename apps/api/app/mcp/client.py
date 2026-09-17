"""MCP client helpers used by LangGraph."""

from __future__ import annotations

from typing import Any

from mcp import Client


def unwrap_structured_content(value: Any) -> Any:
    """Normalize MCP structured_content for scalar, dict and list results."""
    if isinstance(value, dict) and set(value) == {"result"}:
        return value["result"]
    return value


async def call_mcp_tool(
    client: Client,
    tool_name: str,
    arguments: dict[str, Any],
) -> Any:
    """Call one MCP tool and raise a useful error when the tool fails."""
    result = await client.call_tool(tool_name, arguments)

    if result.is_error:
        raise RuntimeError(
            f"MCP tool {tool_name!r} failed: {result.content}"
        )

    return unwrap_structured_content(result.structured_content)
