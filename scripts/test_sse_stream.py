"""STEP 1.4C smoke test for the live SSE investigation stream.

Prerequisite: FastAPI running on http://127.0.0.1:8000
"""

from __future__ import annotations

import json
import sys

import httpx


BASE_URL = "http://127.0.0.1:8000"


def main() -> None:
    payload = {
        "prompt": (
            "Pourquoi Sales_Analytics_033 a échoué "
            "lors de son dernier reload ?"
        ),
        "application_name": "Sales_Analytics_033",
    }

    print("Starting investigation...")

    response = httpx.post(
        f"{BASE_URL}/api/v1/investigations",
        json=payload,
        timeout=10.0,
    )
    response.raise_for_status()

    run = response.json()
    run_id = run["run_id"]

    print(f"Run ID     : {run_id}")
    print(f"Stream URL : {run['stream_url']}")
    print("\nLIVE SSE EVENTS\n" + "=" * 80)

    event_name = None

    with httpx.stream(
        "GET",
        f"{BASE_URL}{run['stream_url']}",
        timeout=None,
    ) as stream:
        stream.raise_for_status()

        for line in stream.iter_lines():
            if not line:
                continue

            if line.startswith(":"):
                print(line)
                continue

            if line.startswith("event:"):
                event_name = line.split(":", 1)[1].strip()
                continue

            if line.startswith("data:"):
                payload = json.loads(line.split(":", 1)[1].strip())
                occurred_at = payload.get("occurred_at") or "-"
                data = payload.get("event_data") or {}

                if event_name == "execution_breakdown":
                    print(
                        f"{occurred_at}  {event_name:<22} "
                        f"TOTAL={data.get('total_ms')} ms | "
                        f"TOOLS={data.get('tool_execution_ms')} ms "
                        f"({data.get('tool_execution_pct')}%) | "
                        f"UNATTRIBUTED={data.get('unattributed_ms')} ms "
                        f"({data.get('unattributed_pct')}%)"
                    )
                else:
                    name = data.get("name", "")
                    duration = data.get("duration_ms")
                    duration_text = (
                        f"{duration} ms" if duration is not None else ""
                    )
                    print(
                        f"{occurred_at}  {event_name:<22} "
                        f"{name:<24} {duration_text}"
                    )

    state = httpx.get(
        f"{BASE_URL}/api/v1/investigations/{run_id}",
        timeout=10.0,
    )
    state.raise_for_status()
    snapshot = state.json()

    print("\n" + "=" * 80)
    print(f"Done        : {snapshot['done']}")
    print(f"Event count : {snapshot['event_count']}")
    print("\nSTEP 1.4C SSE smoke test complete.")


if __name__ == "__main__":
    try:
        main()
    except httpx.ConnectError:
        print(
            "ERROR: FastAPI is not reachable on http://127.0.0.1:8000.\n"
            "Start it first with:\n"
            "python -m uvicorn apps.api.app.main:app --reload --port 8000"
        )
        sys.exit(1)
