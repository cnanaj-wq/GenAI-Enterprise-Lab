"""MCP client helpers used by LangGraph.

STEP 1.8A adds production-oriented resilience:
- per-call timeout
- bounded retries with exponential backoff
- circuit breaker
- retry telemetry callback
"""

from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack
from dataclasses import dataclass
from time import monotonic
from typing import Any, Callable

from mcp import Client

from apps.api.app.config import settings

RetryCallback = Callable[[dict[str, Any]], None]


class MCPToolExecutionError(RuntimeError):
    """Remote MCP tool returned an application-level error."""


class MCPCircuitOpenError(RuntimeError):
    """Circuit breaker is open; remote calls are temporarily rejected."""


@dataclass
class MCPToolCall:
    value: Any
    attempts: int


@dataclass
class MCPConnection:
    client: Client
    stack: AsyncExitStack
    attempts: int

    async def close(self) -> None:
        await self.stack.aclose()


@dataclass
class CircuitBreaker:
    failure_threshold: int
    cooldown_seconds: float
    consecutive_failures: int = 0
    opened_at: float | None = None

    @property
    def state(self) -> str:
        if self.opened_at is None:
            return "CLOSED"

        elapsed = monotonic() - self.opened_at
        if elapsed >= self.cooldown_seconds:
            return "HALF_OPEN"

        return "OPEN"

    def before_call(self) -> None:
        current = self.state

        if current == "OPEN":
            remaining = max(
                self.cooldown_seconds - (monotonic() - (self.opened_at or 0.0)),
                0.0,
            )
            raise MCPCircuitOpenError(f"MCP circuit is OPEN; retry after about {remaining:.1f}s.")

        if current == "HALF_OPEN":
            # Allow one probe request after cooldown.
            self.opened_at = None
            self.consecutive_failures = 0

    def record_success(self) -> None:
        self.consecutive_failures = 0
        self.opened_at = None

    def record_transport_failure(self) -> None:
        self.consecutive_failures += 1
        if self.consecutive_failures >= self.failure_threshold:
            self.opened_at = monotonic()


mcp_circuit_breaker = CircuitBreaker(
    failure_threshold=settings.mcp_circuit_failure_threshold,
    cooldown_seconds=settings.mcp_circuit_cooldown_seconds,
)


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
    """Basic MCP call kept for compatibility with previous steps."""
    result = await client.call_tool(tool_name, arguments)

    if result.is_error:
        raise MCPToolExecutionError(f"MCP tool {tool_name!r} failed: {result.content}")

    return unwrap_structured_content(result.structured_content)


async def call_mcp_tool_resilient(
    client: Client,
    tool_name: str,
    arguments: dict[str, Any],
    *,
    on_retry: RetryCallback | None = None,
    breaker: CircuitBreaker = mcp_circuit_breaker,
) -> MCPToolCall:
    """Call an MCP tool with timeout, retry/backoff and circuit breaker."""

    max_attempts = max(settings.mcp_max_attempts, 1)
    timeout_seconds = max(settings.mcp_call_timeout_seconds, 0.1)
    base_delay_seconds = max(settings.mcp_retry_base_delay_ms, 0) / 1000.0

    breaker.before_call()

    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            result = await asyncio.wait_for(
                client.call_tool(tool_name, arguments),
                timeout=timeout_seconds,
            )

            if result.is_error:
                # Business/tool errors are not connectivity errors.
                raise MCPToolExecutionError(f"MCP tool {tool_name!r} failed: {result.content}")

            breaker.record_success()

            return MCPToolCall(
                value=unwrap_structured_content(result.structured_content),
                attempts=attempt,
            )

        except MCPToolExecutionError:
            raise

        except MCPCircuitOpenError:
            raise

        except Exception as exc:
            last_error = exc
            breaker.record_transport_failure()

            if breaker.state == "OPEN":
                raise MCPCircuitOpenError(
                    f"MCP circuit opened after "
                    f"{breaker.consecutive_failures} consecutive transport failures."
                ) from exc

            if attempt >= max_attempts:
                break

            delay_seconds = base_delay_seconds * (2 ** (attempt - 1))

            if on_retry is not None:
                on_retry(
                    {
                        "tool": tool_name,
                        "attempt": attempt,
                        "next_attempt": attempt + 1,
                        "delay_ms": round(delay_seconds * 1000),
                        "error_type": type(exc).__name__,
                        "error_message": str(exc),
                        "circuit_state": breaker.state,
                    }
                )

            await asyncio.sleep(delay_seconds)

    raise RuntimeError(
        f"MCP tool {tool_name!r} failed after {max_attempts} attempts."
    ) from last_error


async def connect_mcp_resilient(
    endpoint: str | None = None,
    *,
    on_retry: RetryCallback | None = None,
    on_circuit_open: RetryCallback | None = None,
    breaker: CircuitBreaker = mcp_circuit_breaker,
    max_attempts: int | None = None,
    timeout_seconds: float | None = None,
) -> MCPConnection:
    """Open the MCP session with bounded retry/backoff and circuit breaker."""

    endpoint = endpoint or settings.mcp_url
    max_attempts = max(max_attempts or settings.mcp_max_attempts, 1)
    timeout_seconds = max(
        timeout_seconds or settings.mcp_connect_timeout_seconds,
        0.1,
    )
    base_delay_seconds = max(settings.mcp_retry_base_delay_ms, 0) / 1000.0

    breaker.before_call()
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        stack = AsyncExitStack()
        client = Client(endpoint)

        try:
            connected_client = await asyncio.wait_for(
                stack.enter_async_context(client),
                timeout=timeout_seconds,
            )
            breaker.record_success()
            return MCPConnection(
                client=connected_client,
                stack=stack,
                attempts=attempt,
            )

        except MCPCircuitOpenError:
            await stack.aclose()
            raise

        except Exception as exc:
            last_error = exc
            try:
                await stack.aclose()
            except Exception:
                pass

            breaker.record_transport_failure()

            if breaker.state == "OPEN":
                payload = {
                    "phase": "connect",
                    "endpoint": endpoint,
                    "attempt": attempt,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    "circuit_state": breaker.state,
                    "consecutive_failures": breaker.consecutive_failures,
                    "cooldown_seconds": breaker.cooldown_seconds,
                }
                if on_circuit_open is not None:
                    on_circuit_open(payload)

                raise MCPCircuitOpenError(
                    f"MCP circuit opened while connecting to {endpoint} after "
                    f"{breaker.consecutive_failures} consecutive failures."
                ) from exc

            if attempt >= max_attempts:
                break

            delay_seconds = base_delay_seconds * (2 ** (attempt - 1))

            if on_retry is not None:
                on_retry(
                    {
                        "phase": "connect",
                        "endpoint": endpoint,
                        "attempt": attempt,
                        "next_attempt": attempt + 1,
                        "delay_ms": round(delay_seconds * 1000),
                        "error_type": type(exc).__name__,
                        "error_message": str(exc),
                        "circuit_state": breaker.state,
                    }
                )

            await asyncio.sleep(delay_seconds)

    raise RuntimeError(
        f"Unable to connect to MCP endpoint {endpoint!r} after {max_attempts} attempts."
    ) from last_error
