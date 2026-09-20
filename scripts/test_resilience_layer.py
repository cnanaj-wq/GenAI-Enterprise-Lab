"""STEP 1.8A smoke tests for retry/backoff and circuit breaker."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from apps.api.app.config import settings
from apps.api.app.mcp.client import (
    CircuitBreaker,
    MCPCircuitOpenError,
    call_mcp_tool_resilient,
)


class FakeClient:
    def __init__(self, failures_before_success: int) -> None:
        self.failures_before_success = failures_before_success
        self.calls = 0

    async def call_tool(self, tool_name: str, arguments: dict):
        self.calls += 1
        if self.calls <= self.failures_before_success:
            raise ConnectionError("synthetic transport failure")

        return SimpleNamespace(
            is_error=False,
            structured_content={"result": {"ok": True, "tool": tool_name}},
            content=[],
        )


async def retry_test() -> None:
    original_attempts = settings.mcp_max_attempts
    original_delay = settings.mcp_retry_base_delay_ms

    settings.mcp_max_attempts = 3
    settings.mcp_retry_base_delay_ms = 1

    retries = []
    client = FakeClient(failures_before_success=2)
    breaker = CircuitBreaker(failure_threshold=10, cooldown_seconds=1.0)

    try:
        result = await call_mcp_tool_resilient(
            client,
            "synthetic_tool",
            {"id": 42},
            on_retry=retries.append,
            breaker=breaker,
        )
    finally:
        settings.mcp_max_attempts = original_attempts
        settings.mcp_retry_base_delay_ms = original_delay

    assert result.attempts == 3
    assert result.value["ok"] is True
    assert len(retries) == 2
    assert breaker.state == "CLOSED"

    print("RETRY TEST")
    print("=" * 72)
    print(f"attempts : {result.attempts}")
    print(f"retries  : {len(retries)}")
    print(f"circuit  : {breaker.state}")
    print("status   : PASS")


async def circuit_test() -> None:
    original_attempts = settings.mcp_max_attempts
    original_delay = settings.mcp_retry_base_delay_ms

    settings.mcp_max_attempts = 3
    settings.mcp_retry_base_delay_ms = 1

    client = FakeClient(failures_before_success=999)
    breaker = CircuitBreaker(failure_threshold=2, cooldown_seconds=30.0)

    try:
        try:
            await call_mcp_tool_resilient(
                client,
                "always_fails",
                {},
                breaker=breaker,
            )
        except MCPCircuitOpenError:
            pass
        else:
            raise AssertionError("Circuit breaker should have opened.")

        assert breaker.state == "OPEN"
        assert breaker.consecutive_failures == 2

        calls_before = client.calls

        try:
            await call_mcp_tool_resilient(
                client,
                "always_fails",
                {},
                breaker=breaker,
            )
        except MCPCircuitOpenError:
            pass
        else:
            raise AssertionError("Open circuit should reject immediately.")

        assert client.calls == calls_before

    finally:
        settings.mcp_max_attempts = original_attempts
        settings.mcp_retry_base_delay_ms = original_delay

    print("\nCIRCUIT BREAKER TEST")
    print("=" * 72)
    print(f"failures : {breaker.consecutive_failures}")
    print(f"circuit  : {breaker.state}")
    print("status   : PASS")


async def main() -> None:
    await retry_test()
    await circuit_test()
    print("\nSTEP 1.8A RESILIENCE LAYER: VALIDATED")


if __name__ == "__main__":
    asyncio.run(main())
