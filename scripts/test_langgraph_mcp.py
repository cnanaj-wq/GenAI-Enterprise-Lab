"""STEP 1.7B smoke test: verify LangGraph can consume MCP tools."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mcp import Client

from apps.api.app.config import settings


async def main() -> None:
    async with Client(settings.mcp_url) as client:
        print("MCP")
        print("=" * 72)
        print(f"Endpoint         : {settings.mcp_url}")
        print(f"Protocol version : {client.protocol_version}")
        print(f"Server info      : {client.server_info}")

        app = await client.call_tool(
            "get_application",
            {"application_name": "Sales_Analytics_033"},
        )

        print("\nget_application structured_content")
        print("=" * 72)
        print(app.structured_content)

        if app.is_error:
            raise RuntimeError(str(app.content))

        print("\nSTEP 1.7B MCP client prerequisite validated.")
        print(
            "Now run the full workflow from the Next.js cockpit. "
            "The live graph should show cyan MCP spans."
        )


if __name__ == "__main__":
    asyncio.run(main())
