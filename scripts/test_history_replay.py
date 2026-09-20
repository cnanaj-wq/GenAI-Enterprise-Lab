"""STEP 1.9 smoke test for History & Replay API."""

from __future__ import annotations

import sys
from pathlib import Path

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


API = "http://127.0.0.1:8000"


def main() -> None:
    history_response = httpx.get(
        f"{API}/api/v1/investigations/history",
        params={"limit": 10},
        timeout=10.0,
    )
    history_response.raise_for_status()
    history = history_response.json()

    print("HISTORY")
    print("=" * 72)
    print(f"count : {history['count']}")

    if history["count"] == 0:
        raise RuntimeError("No persisted traces found. Run at least one investigation first.")

    trace_id = history["items"][0]["trace_id"]
    print(f"trace : {trace_id}")

    replay_response = httpx.get(
        f"{API}/api/v1/investigations/traces/{trace_id}/replay",
        timeout=10.0,
    )
    replay_response.raise_for_status()
    replay = replay_response.json()

    print("\nREPLAY")
    print("=" * 72)
    print(f"trace status : {replay['trace']['status']}")
    print(f"spans        : {len(replay['spans'])}")
    print(f"events       : {len(replay['events'])}")
    print(f"summary      : {bool(replay.get('summary'))}")
    print(f"diagnosis    : {bool(replay.get('diagnosis'))}")
    print(f"breakdown    : {bool(replay.get('execution_breakdown'))}")

    assert replay["replay"] is True
    assert len(replay["spans"]) > 0
    assert len(replay["events"]) > 0

    print("\nSTEP 1.9 HISTORY & REPLAY: VALIDATED")


if __name__ == "__main__":
    main()
