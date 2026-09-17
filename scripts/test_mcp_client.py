"""STEP 1.7A smoke test for the MCP v2 Streamable HTTP server."""

from __future__ import annotations

import anyio
from mcp import Client

MCP_URL = "http://127.0.0.1:8001/mcp"


def _unwrap(value):
    if isinstance(value, dict) and "result" in value and len(value) == 1:
        return value["result"]
    return value


async def main() -> None:
    async with Client(MCP_URL) as client:
        print("MCP connection")
        print("=" * 72)
        print(f"Protocol version : {client.protocol_version}")
        print(f"Server info      : {client.server_info}")

        tools_result = await client.list_tools()

        print("\nExposed tools")
        print("=" * 72)
        for tool in tools_result.tools:
            print(f"- {tool.name}")
            print(f"  description: {tool.description}")
            print(f"  input schema: {tool.input_schema}")

        expected = {
            "get_application",
            "get_reload_history",
            "get_reload_logs",
            "get_incident",
            "get_jira_ticket",
            "check_dependencies",
        }
        actual = {tool.name for tool in tools_result.tools}
        missing = expected - actual
        if missing:
            raise RuntimeError(f"Missing MCP tools: {sorted(missing)}")

        print("\nCalling get_application through MCP")
        print("=" * 72)
        app_result = await client.call_tool(
            "get_application",
            {"application_name": "Sales_Analytics_033"},
        )
        if app_result.is_error:
            raise RuntimeError(str(app_result.content))
        app = _unwrap(app_result.structured_content)
        print(app)
        if not app:
            raise RuntimeError("Application not returned through MCP.")

        application_id = int(app["application_id"])

        print("\nCalling get_reload_history through MCP")
        print("=" * 72)
        history_result = await client.call_tool(
            "get_reload_history",
            {
                "application_id": application_id,
                "status": "FAILED",
                "limit": 1,
            },
        )
        if history_result.is_error:
            raise RuntimeError(str(history_result.content))
        history = _unwrap(history_result.structured_content)
        print(history)
        if not history:
            raise RuntimeError("No failed reload returned through MCP.")

        reload_id = int(history[0]["reload_id"])

        print("\nCalling get_reload_logs through MCP")
        print("=" * 72)
        logs_result = await client.call_tool(
            "get_reload_logs",
            {"reload_id": reload_id, "limit": 20},
        )
        if logs_result.is_error:
            raise RuntimeError(str(logs_result.content))
        print(_unwrap(logs_result.structured_content))

        print("\nReading ops://manifest")
        print("=" * 72)
        resource = await client.read_resource("ops://manifest")
        print(resource)

        print("\nSTEP 1.7A MCP smoke test complete.")


if __name__ == "__main__":
    anyio.run(main)
