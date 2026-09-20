"""STEP 1.10 smoke test: compare two persisted investigation traces."""

from __future__ import annotations

import httpx

API = "http://127.0.0.1:8000"


def replay(trace_id: str) -> dict:
    response = httpx.get(
        f"{API}/api/v1/investigations/traces/{trace_id}/replay",
        timeout=10.0,
    )
    response.raise_for_status()
    return response.json()


def metric(replay_payload: dict) -> dict:
    trace = replay_payload["trace"]
    breakdown = replay_payload.get("execution_breakdown") or {}
    events = replay_payload.get("events") or []
    spans = replay_payload.get("spans") or []

    input_tokens = int(trace.get("input_tokens") or 0)
    output_tokens = int(trace.get("output_tokens") or 0)

    resilience = "FAILED" if trace["status"] == "ERROR" else "OK"
    if trace["status"] != "ERROR":
        if any(e["event_type"] == "fallback_used" for e in events):
            resilience = "FALLBACK"
        elif any(e["event_type"] == "mcp_retry_scheduled" for e in events):
            resilience = "RETRY"

    return {
        "trace": trace["trace_id"],
        "status": trace["status"],
        "resilience": resilience,
        "model": trace.get("model"),
        "duration_ms": int(trace.get("duration_ms") or 0),
        "mcp_ms": int(breakdown.get("mcp_duration_ms") or 0),
        "llm_ms": int(breakdown.get("llm_duration_ms") or 0),
        "tokens": input_tokens + output_tokens,
        "cost": float(trace.get("estimated_cost_usd") or 0),
        "errors": sum(1 for s in spans if s["status"] == "ERROR")
        + sum(1 for e in events if e["event_type"] == "run_error"),
    }


def delta(a: float, b: float) -> str:
    if a == 0:
        return "n/a" if b != 0 else "0.0%"
    return f"{((b - a) / a) * 100:+.1f}%"


def main() -> None:
    history_response = httpx.get(
        f"{API}/api/v1/investigations/history",
        params={"limit": 20},
        timeout=10.0,
    )
    history_response.raise_for_status()
    items = history_response.json()["items"]

    if len(items) < 2:
        raise RuntimeError("At least two persisted traces are required.")

    a = metric(replay(items[0]["trace_id"]))
    b = metric(replay(items[1]["trace_id"]))

    print("TRACE COMPARE")
    print("=" * 72)
    print(f"A : {a['trace']}  {a['status']}  {a['resilience']}")
    print(f"B : {b['trace']}  {b['status']}  {b['resilience']}")
    print()
    print(
        f"Duration : {a['duration_ms']} -> {b['duration_ms']} ms  {delta(a['duration_ms'], b['duration_ms'])}"
    )
    print(f"MCP      : {a['mcp_ms']} -> {b['mcp_ms']} ms  {delta(a['mcp_ms'], b['mcp_ms'])}")
    print(f"LLM      : {a['llm_ms']} -> {b['llm_ms']} ms  {delta(a['llm_ms'], b['llm_ms'])}")
    print(f"Tokens   : {a['tokens']} -> {b['tokens']}  {delta(a['tokens'], b['tokens'])}")
    print(f"Cost     : ${a['cost']:.6f} -> ${b['cost']:.6f}  {delta(a['cost'], b['cost'])}")
    print(f"Errors   : {a['errors']} -> {b['errors']}")
    print()
    print("STEP 1.10 COMPARE DATA: VALIDATED")


if __name__ == "__main__":
    main()
