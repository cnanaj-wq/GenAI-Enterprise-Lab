from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.api.app.database import engine


@dataclass
class Result:
    name: str
    started_at: datetime
    finished_at: datetime
    duration_ms: int
    status: str
    error_message: str | None


def now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def command(name: str) -> str:
    resolved = shutil.which(name)
    if resolved:
        return resolved

    if os.name == "nt":
        resolved = shutil.which(f"{name}.cmd")
        if resolved:
            return resolved

    raise RuntimeError(f"Command not found: {name}")


def run_check(name: str, cmd: list[str], cwd: Path) -> Result:
    started_at = now()
    timer = perf_counter()

    print()
    print(f"[{started_at.isoformat()}] {name}")
    print("=" * 72)
    print(" ".join(cmd))

    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    result = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        check=False,
    )

    finished_at = now()
    duration_ms = round((perf_counter() - timer) * 1000)

    if result.stdout:
        print(result.stdout.rstrip())

    if result.stderr:
        print(result.stderr.rstrip())

    status = "PASS" if result.returncode == 0 else "FAIL"

    error_message = None
    if status == "FAIL":
        combined = "\n".join(
            part.strip() for part in (result.stdout, result.stderr) if part and part.strip()
        )
        error_message = combined[-4000:] if combined else f"{name} returned {result.returncode}."

    print(f"{name}: {status} ({duration_ms} ms)")

    return Result(
        name=name,
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=duration_ms,
        status=status,
        error_message=error_message,
    )


def persist(
    pipeline_id, started_at: datetime, finished_at: datetime, results: list[Result]
) -> None:
    overall = "PASS" if all(result.status == "PASS" for result in results) else "FAIL"

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO delivery.ci_pipeline_runs (
                    pipeline_id,
                    source_type,
                    branch,
                    commit_sha,
                    commit_message,
                    triggered_by,
                    trigger_type,
                    push_at,
                    started_at,
                    finished_at,
                    duration_ms,
                    status
                )
                VALUES (
                    :pipeline_id,
                    'REAL_LOCAL',
                    :branch,
                    :commit_sha,
                    :commit_message,
                    :triggered_by,
                    'MANUAL',
                    NULL,
                    :started_at,
                    :finished_at,
                    :duration_ms,
                    :status
                );
                """
            ),
            {
                "pipeline_id": pipeline_id,
                "branch": git("branch", "--show-current"),
                "commit_sha": git("rev-parse", "HEAD"),
                "commit_message": git("log", "-1", "--pretty=%s"),
                "triggered_by": os.getenv("USERNAME") or os.getenv("USER") or "local",
                "started_at": started_at,
                "finished_at": finished_at,
                "duration_ms": round((finished_at - started_at).total_seconds() * 1000),
                "status": overall,
            },
        )

        for result in results:
            connection.execute(
                text(
                    """
                    INSERT INTO delivery.ci_pipeline_checks (
                        pipeline_id,
                        check_name,
                        started_at,
                        finished_at,
                        duration_ms,
                        status,
                        error_message
                    )
                    VALUES (
                        :pipeline_id,
                        :check_name,
                        :started_at,
                        :finished_at,
                        :duration_ms,
                        :status,
                        :error_message
                    );
                    """
                ),
                {
                    "pipeline_id": pipeline_id,
                    "check_name": result.name,
                    "started_at": result.started_at,
                    "finished_at": result.finished_at,
                    "duration_ms": result.duration_ms,
                    "status": result.status,
                    "error_message": result.error_message,
                },
            )


def main() -> int:
    pipeline_id = uuid4()
    started_at = now()
    npm = command("npm")

    # Limit Ruff to actual Python project code.
    ruff_targets = [
        "apps/api",
        "apps/mcp",
        "data/generators",
        "scripts",
        "tests",
    ]
    ruff_targets = [path for path in ruff_targets if (ROOT / path).exists()]

    checks = [
        (
            "RUFF",
            [sys.executable, "-m", "ruff", "check", *ruff_targets],
            ROOT,
        ),
        (
            "PYTEST",
            [sys.executable, "-m", "pytest", "-q"],
            ROOT,
        ),
        (
            "ESLINT",
            [npm, "run", "lint"],
            ROOT / "apps" / "web",
        ),
        (
            "NEXTJS_BUILD",
            [npm, "run", "build"],
            ROOT / "apps" / "web",
        ),
    ]

    print("MODULE 1 — FINAL QUALITY GATE")
    print("=" * 72)
    print("Branch :", git("branch", "--show-current"))
    print("Commit :", git("rev-parse", "--short", "HEAD"))

    results = [run_check(*check) for check in checks]
    finished_at = now()

    try:
        persist(pipeline_id, started_at, finished_at, results)
        recorded = True
    except Exception as exc:
        recorded = False
        print()
        print("Project Health persistence failed:")
        print(f"{type(exc).__name__}: {exc}")

    print()
    print("FINAL QUALITY GATE")
    print("=" * 72)

    for result in results:
        print(f"{result.name:14} {result.status:4} {result.duration_ms:>8} ms")

    passed = all(result.status == "PASS" for result in results)

    print()
    print("Project Health :", "RECORDED" if recorded else "NOT RECORDED")
    print("Overall        :", "PASS" if passed else "FAIL")
    print()
    print("MODULE 1 QUALITY GATE:", "PASS" if passed else "FAIL")

    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
