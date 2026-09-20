"""STEP 1.12 smoke test for PROJECT HEALTH."""

from __future__ import annotations

import httpx

API = "http://127.0.0.1:8000"


def main() -> None:
    summary = httpx.get(
        f"{API}/api/v1/project-health/summary",
        timeout=10.0,
    )
    summary.raise_for_status()
    payload = summary.json()

    pipelines = httpx.get(
        f"{API}/api/v1/project-health/pipelines",
        params={"limit": 5},
        timeout=10.0,
    )
    pipelines.raise_for_status()
    history = pipelines.json()

    print("PROJECT HEALTH")
    print("=" * 72)
    print(f"overall          : {payload['overall']}")
    print(f"branch           : {payload['git']['branch']}")
    print(f"git sync         : {payload['git']['sync_status']}")
    print(f"dirty files      : {payload['git']['working_tree_files']}")
    print(f"CI success 7d    : {payload['stats']['success_rate_7d']} %")
    print(f"alerts           : {len(payload['alerts'])}")
    print(f"pipelines loaded : {history['count']}")
    print()

    for name, component in payload["runtime"].items():
        print(f"{name:12} : {component['status']} :{component['port']}")

    assert history["count"] > 0
    assert "fastapi" in payload["runtime"]
    assert "git" in payload

    print("\nSTEP 1.12 PROJECT HEALTH: VALIDATED")


if __name__ == "__main__":
    main()
