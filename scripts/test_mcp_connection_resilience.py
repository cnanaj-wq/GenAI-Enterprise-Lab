"""STEP 1.8B: validate MCP connection retry and circuit breaker."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from apps.api.app.mcp.client import (
    CircuitBreaker,
    MCPCircuitOpenError,
    connect_mcp_resilient,
)


async def main() -> None:
    retries: list[dict] = []
    opened: list[dict] = []
    breaker = CircuitBreaker(failure_threshold=3, cooldown_seconds=30.0)

    try:
        await connect_mcp_resilient(
            "http://127.0.0.1:65530/mcp",
            on_retry=retries.append,
            on_circuit_open=opened.append,
            breaker=breaker,
            max_attempts=3,
            timeout_seconds=0.5,
        )
    except MCPCircuitOpenError:
        pass
    else:
        raise AssertionError("Expected the MCP connection circuit to open.")

    assert len(retries) == 2, retries
    assert len(opened) == 1, opened
    assert breaker.state == "OPEN"

    print("MCP CONNECTION RESILIENCE")
    print("=" * 72)
    print(f"retries       : {len(retries)}")
    print(f"circuit events: {len(opened)}")
    print(f"circuit state : {breaker.state}")
    print("status        : PASS")
    print()
    print("STEP 1.8B CONNECTION RESILIENCE: VALIDATED")


if __name__ == "__main__":
    asyncio.run(main())
