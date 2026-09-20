"""Generate deterministic synthetic CI/CD history for PROJECT HEALTH."""

from __future__ import annotations

import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy import text

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from apps.api.app.database import engine

SEED = 42
DAYS = 90
BRANCH = "module-1-agentic-ai"

CHECKS = [
    ("RUFF", 4_000, 2_000),
    ("PYTEST", 18_000, 8_000),
    ("ESLINT", 7_000, 3_000),
    ("NEXTJS_BUILD", 30_000, 12_000),
]

MESSAGES = [
    "feat: add LangGraph orchestration",
    "feat: expose enterprise tools through MCP",
    "feat: add live observability cockpit",
    "feat: add OpenAI grounded diagnosis",
    "feat: add MCP resilience and circuit breaker",
    "feat: add deterministic LLM fallback",
    "feat: add history and replay",
    "feat: add trace comparison",
    "fix: harden optional SQL filters",
    "fix: restore MCP connection recovery",
    "docs: update Module 1 architecture",
    "test: extend fault injection scenarios",
]

FAIL_MESSAGES = {
    "RUFF": "Ruff detected lint/import violations.",
    "PYTEST": "One or more automated tests failed.",
    "ESLINT": "ESLint detected frontend quality violations.",
    "NEXTJS_BUILD": "Next.js production build failed.",
}


def sha(rng: random.Random) -> str:
    return "".join(rng.choice("0123456789abcdef") for _ in range(40))


def main() -> None:
    rng = random.Random(SEED)
    now = datetime.now(timezone.utc).replace(microsecond=0)

    pipelines: list[dict] = []
    checks: list[dict] = []

    # Roughly 2 deliveries/day with realistic gaps.
    for day_offset in range(DAYS - 1, -1, -1):
        day = now - timedelta(days=day_offset)
        count = rng.choices([0, 1, 2, 3, 4], weights=[5, 20, 45, 25, 5], k=1)[0]

        for delivery_index in range(count):
            started = day.replace(
                hour=rng.randint(8, 21),
                minute=rng.randint(0, 59),
                second=rng.randint(0, 59),
            )

            pipeline_id = uuid4()
            commit_sha = sha(rng)
            overall_roll = rng.random()

            if overall_roll < 0.90:
                overall_status = "PASS"
            elif overall_roll < 0.96:
                overall_status = "WARNING"
            else:
                overall_status = "FAIL"

            failing_check = rng.choice(CHECKS)[0] if overall_status == "FAIL" else None
            warning_check = rng.choice(CHECKS)[0] if overall_status == "WARNING" else None

            cursor = started
            pipeline_checks: list[dict] = []

            for check_name, base_ms, spread_ms in CHECKS:
                # Small orchestration gap before each check.
                cursor += timedelta(milliseconds=rng.randint(300, 1_700))
                check_start = cursor
                duration_ms = max(500, int(rng.gauss(base_ms, spread_ms)))
                check_end = check_start + timedelta(milliseconds=duration_ms)

                if check_name == failing_check:
                    check_status = "FAIL"
                    error_message = FAIL_MESSAGES[check_name]
                elif check_name == warning_check:
                    check_status = "WARNING"
                    error_message = f"{check_name} completed with non-blocking warnings."
                else:
                    check_status = "PASS"
                    error_message = None

                pipeline_checks.append(
                    {
                        "pipeline_id": pipeline_id,
                        "check_name": check_name,
                        "started_at": check_start,
                        "finished_at": check_end,
                        "duration_ms": duration_ms,
                        "status": check_status,
                        "error_message": error_message,
                    }
                )
                cursor = check_end

                # Stop a FAIL pipeline after the failing quality gate, like fail-fast CI.
                if check_status == "FAIL":
                    break

            finished = cursor
            duration_ms = int((finished - started).total_seconds() * 1000)
            push_at = started - timedelta(seconds=rng.randint(2, 18))

            pipelines.append(
                {
                    "pipeline_id": pipeline_id,
                    "source_type": "SYNTHETIC",
                    "branch": BRANCH,
                    "commit_sha": commit_sha,
                    "commit_message": rng.choice(MESSAGES),
                    "triggered_by": "synthetic-developer",
                    "trigger_type": rng.choices(
                        ["PUSH", "PULL_REQUEST", "MANUAL"],
                        weights=[80, 15, 5],
                        k=1,
                    )[0],
                    "push_at": push_at,
                    "started_at": started,
                    "finished_at": finished,
                    "duration_ms": duration_ms,
                    "status": overall_status,
                }
            )
            checks.extend(pipeline_checks)

    with engine.begin() as connection:
        connection.execute(text("DELETE FROM delivery.ci_pipeline_checks;"))
        connection.execute(
            text("DELETE FROM delivery.ci_pipeline_runs WHERE source_type = 'SYNTHETIC';")
        )

        for row in pipelines:
            connection.execute(
                text(
                    """
                    INSERT INTO delivery.ci_pipeline_runs (
                        pipeline_id, source_type, branch, commit_sha, commit_message,
                        triggered_by, trigger_type, push_at, started_at, finished_at,
                        duration_ms, status
                    )
                    VALUES (
                        :pipeline_id, :source_type, :branch, :commit_sha, :commit_message,
                        :triggered_by, :trigger_type, :push_at, :started_at, :finished_at,
                        :duration_ms, :status
                    );
                    """
                ),
                row,
            )

        for row in checks:
            connection.execute(
                text(
                    """
                    INSERT INTO delivery.ci_pipeline_checks (
                        pipeline_id, check_name, started_at, finished_at,
                        duration_ms, status, error_message
                    )
                    VALUES (
                        :pipeline_id, :check_name, :started_at, :finished_at,
                        :duration_ms, :status, :error_message
                    );
                    """
                ),
                row,
            )

    passed = sum(1 for row in pipelines if row["status"] == "PASS")
    failed = sum(1 for row in pipelines if row["status"] == "FAIL")
    warnings = sum(1 for row in pipelines if row["status"] == "WARNING")

    print("SYNTHETIC CI/CD HISTORY")
    print("=" * 72)
    print(f"seed       : {SEED}")
    print(f"days       : {DAYS}")
    print(f"pipelines  : {len(pipelines)}")
    print(f"checks     : {len(checks)}")
    print(f"PASS       : {passed}")
    print(f"WARNING    : {warnings}")
    print(f"FAIL       : {failed}")
    print("status     : GENERATED")


if __name__ == "__main__":
    main()
