"""In-memory live event broker for Server-Sent Events (SSE).

STEP 1.4C uses an in-process broker for local development.
Production multi-worker deployment will later replace this with a shared
transport (Redis / PubSub / Kafka) while keeping the same event contract.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID


@dataclass
class RunStreamState:
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    events: list[dict[str, Any]] = field(default_factory=list)
    subscribers: set[asyncio.Queue[dict[str, Any]]] = field(default_factory=set)
    done: bool = False


class LiveEventBroker:
    """Buffers events and fans them out to connected SSE subscribers."""

    def __init__(self) -> None:
        self._runs: dict[UUID, RunStreamState] = {}

    def create_run(self, run_id: UUID) -> None:
        self._runs[run_id] = RunStreamState()

    def exists(self, run_id: UUID) -> bool:
        return run_id in self._runs

    def publish(self, run_id: UUID, event: dict[str, Any]) -> None:
        state = self._runs.get(run_id)
        if state is None:
            return

        state.events.append(event)

        for queue in tuple(state.subscribers):
            queue.put_nowait(event)

    def mark_done(self, run_id: UUID) -> None:
        state = self._runs.get(run_id)
        if state is not None:
            state.done = True

    def snapshot(self, run_id: UUID) -> dict[str, Any] | None:
        state = self._runs.get(run_id)
        if state is None:
            return None

        return {
            "run_id": str(run_id),
            "created_at": state.created_at.isoformat(),
            "done": state.done,
            "event_count": len(state.events),
            "events": list(state.events),
        }

    def subscribe(
        self,
        run_id: UUID,
    ) -> tuple[
        asyncio.Queue[dict[str, Any]],
        list[dict[str, Any]],
        bool,
    ]:
        state = self._runs[run_id]
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        state.subscribers.add(queue)

        # The snapshot is captured after the subscriber is registered.
        # New events will therefore go into the queue and won't be lost.
        buffered = list(state.events)
        return queue, buffered, state.done

    def unsubscribe(
        self,
        run_id: UUID,
        queue: asyncio.Queue[dict[str, Any]],
    ) -> None:
        state = self._runs.get(run_id)
        if state is not None:
            state.subscribers.discard(queue)

    def is_done(self, run_id: UUID) -> bool:
        state = self._runs.get(run_id)
        return bool(state and state.done)


live_event_broker = LiveEventBroker()
