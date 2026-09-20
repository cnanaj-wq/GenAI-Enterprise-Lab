"""PROJECT HEALTH / CI-CD Control Tower endpoints."""

from __future__ import annotations

import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from apps.api.app.database import engine

router = APIRouter(prefix="/api/v1/project-health", tags=["project-health"])

PROJECT_ROOT = Path(__file__).resolve().parents[4]


def _run_git(*args: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    if completed.returncode != 0:
        return None

    return completed.stdout.strip()


def _tcp_health(host: str, port: int, timeout: float = 0.35) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _git_snapshot() -> dict[str, Any]:
    branch = _run_git("branch", "--show-current") or "unknown"
    head_sha = _run_git("rev-parse", "HEAD")
    short_sha = _run_git("rev-parse", "--short", "HEAD")
    commit_message = _run_git("log", "-1", "--pretty=%s")
    commit_at = _run_git("log", "-1", "--pretty=%cI")
    status_lines = (_run_git("status", "--porcelain") or "").splitlines()

    ahead = 0
    behind = 0
    remote_ref = f"origin/{branch}"

    counts = _run_git(
        "rev-list",
        "--left-right",
        "--count",
        f"HEAD...{remote_ref}",
    )
    if counts:
        parts = counts.split()
        if len(parts) == 2:
            ahead = int(parts[0])
            behind = int(parts[1])

    remote_sha = _run_git("rev-parse", remote_ref)
    remote_commit_at = _run_git("log", "-1", "--pretty=%cI", remote_ref)

    if branch == "unknown":
        sync_status = "UNKNOWN"
    elif behind > 0:
        sync_status = "BEHIND"
    elif ahead > 0:
        sync_status = "PUSH_REQUIRED"
    elif status_lines:
        sync_status = "DIRTY"
    else:
        sync_status = "SYNCED"

    return {
        "branch": branch,
        "head_sha": head_sha,
        "short_sha": short_sha,
        "commit_message": commit_message,
        "commit_at": commit_at,
        "working_tree_files": len(status_lines),
        "working_tree_dirty": bool(status_lines),
        "ahead": ahead,
        "behind": behind,
        "remote_sha": remote_sha,
        "remote_commit_at": remote_commit_at,
        "sync_status": sync_status,
        "note": (
            "remote_commit_at is the timestamp of the commit visible on the "
            "remote-tracking branch; Git itself does not store the actual push timestamp."
        ),
    }


def _runtime_snapshot() -> dict[str, Any]:
    postgres_ok = False
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1")).scalar_one()
        postgres_ok = True
    except SQLAlchemyError:
        postgres_ok = False

    return {
        "fastapi": {
            "status": "HEALTHY",
            "port": 8000,
        },
        "nextjs": {
            "status": "HEALTHY" if _tcp_health("127.0.0.1", 3000) else "DOWN",
            "port": 3000,
        },
        "mcp": {
            "status": "HEALTHY" if _tcp_health("127.0.0.1", 8001) else "DOWN",
            "port": 8001,
        },
        "postgresql": {
            "status": "HEALTHY" if postgres_ok else "DOWN",
            "port": 5432,
        },
    }


def _load_pipeline_rows(limit: int) -> list[dict[str, Any]]:
    with engine.connect() as connection:
        rows = (
            connection.execute(
                text(
                    """
                SELECT
                    p.pipeline_id,
                    p.source_type,
                    p.branch,
                    p.commit_sha,
                    p.commit_message,
                    p.triggered_by,
                    p.trigger_type,
                    p.push_at,
                    p.started_at,
                    p.finished_at,
                    p.duration_ms,
                    p.status
                FROM delivery.ci_pipeline_runs p
                ORDER BY p.started_at DESC
                LIMIT :limit;
                """
                ),
                {"limit": limit},
            )
            .mappings()
            .all()
        )

        results = []
        for row in rows:
            pipeline = dict(row)
            check_rows = (
                connection.execute(
                    text(
                        """
                    SELECT
                        check_id,
                        check_name,
                        started_at,
                        finished_at,
                        duration_ms,
                        status,
                        error_message
                    FROM delivery.ci_pipeline_checks
                    WHERE pipeline_id = :pipeline_id
                    ORDER BY started_at;
                    """
                    ),
                    {"pipeline_id": row["pipeline_id"]},
                )
                .mappings()
                .all()
            )
            pipeline["checks"] = [dict(check) for check in check_rows]
            results.append(pipeline)

    return results


def _stats() -> dict[str, Any]:
    with engine.connect() as connection:
        row = (
            connection.execute(
                text(
                    """
                SELECT
                    COUNT(*) FILTER (
                        WHERE started_at >= NOW() - INTERVAL '7 days'
                    ) AS pipelines_7d,
                    COUNT(*) FILTER (
                        WHERE started_at >= NOW() - INTERVAL '7 days'
                          AND status = 'PASS'
                    ) AS pass_7d,
                    AVG(duration_ms) FILTER (
                        WHERE started_at >= NOW() - INTERVAL '30 days'
                    ) AS avg_duration_30d,
                    MAX(started_at) AS last_pipeline_at
                FROM delivery.ci_pipeline_runs;
                """
                )
            )
            .mappings()
            .one()
        )

    pipelines_7d = int(row["pipelines_7d"] or 0)
    pass_7d = int(row["pass_7d"] or 0)
    success_rate_7d = round(100.0 * pass_7d / pipelines_7d, 1) if pipelines_7d else 0.0

    return {
        "pipelines_7d": pipelines_7d,
        "success_rate_7d": success_rate_7d,
        "avg_duration_30d_ms": int(row["avg_duration_30d"] or 0),
        "last_pipeline_at": row["last_pipeline_at"],
    }


def _alerts(
    git: dict[str, Any],
    runtime: dict[str, Any],
    latest_pipeline: dict[str, Any] | None,
    stats: dict[str, Any],
) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    alerts: list[dict[str, Any]] = []

    if git["working_tree_dirty"]:
        alerts.append(
            {
                "severity": "WARNING",
                "code": "GIT_DIRTY",
                "title": "Working tree non commitée",
                "message": f"{git['working_tree_files']} fichier(s) modifié(s) localement.",
                "detected_at": now,
            }
        )

    if git["ahead"] > 0:
        alerts.append(
            {
                "severity": "WARNING",
                "code": "PUSH_REQUIRED",
                "title": "Push Git requis",
                "message": f"La branche locale a {git['ahead']} commit(s) d'avance.",
                "detected_at": now,
            }
        )

    if git["behind"] > 0:
        alerts.append(
            {
                "severity": "CRITICAL",
                "code": "BRANCH_BEHIND",
                "title": "Branche locale en retard",
                "message": f"La branche locale a {git['behind']} commit(s) de retard.",
                "detected_at": now,
            }
        )

    for component_name, component in runtime.items():
        if component["status"] != "HEALTHY":
            alerts.append(
                {
                    "severity": "CRITICAL",
                    "code": f"{component_name.upper()}_DOWN",
                    "title": f"{component_name} indisponible",
                    "message": f"Le port {component['port']} ne répond pas.",
                    "detected_at": now,
                }
            )

    if latest_pipeline and latest_pipeline["status"] == "FAIL":
        alerts.append(
            {
                "severity": "CRITICAL",
                "code": "LATEST_CI_FAILED",
                "title": "Dernière livraison en échec",
                "message": (
                    f"Pipeline {str(latest_pipeline['pipeline_id'])[:8]} : "
                    f"{latest_pipeline['commit_message']}"
                ),
                "detected_at": now,
            }
        )

    if stats["pipelines_7d"] >= 3 and stats["success_rate_7d"] < 90.0:
        alerts.append(
            {
                "severity": "WARNING",
                "code": "CI_SUCCESS_RATE_LOW",
                "title": "Taux CI sous le seuil",
                "message": (
                    f"Seulement {stats['success_rate_7d']} % des pipelines "
                    "des 7 derniers jours sont PASS."
                ),
                "detected_at": now,
            }
        )

    return alerts


@router.get("/summary")
def project_health_summary():
    try:
        git = _git_snapshot()
        runtime = _runtime_snapshot()
        pipelines = _load_pipeline_rows(1)
        latest_pipeline = pipelines[0] if pipelines else None
        stats = _stats()
        alerts = _alerts(git, runtime, latest_pipeline, stats)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Project Health tables are unavailable. "
                "Apply migration 005_project_health_ci.sql and generate history."
            ),
        ) from exc

    overall = "HEALTHY"
    if any(alert["severity"] == "CRITICAL" for alert in alerts):
        overall = "CRITICAL"
    elif alerts:
        overall = "WARNING"

    return {
        "generated_at": datetime.now(timezone.utc),
        "overall": overall,
        "git": git,
        "runtime": runtime,
        "stats": stats,
        "latest_pipeline": latest_pipeline,
        "alerts": alerts,
    }


@router.get("/pipelines")
def list_pipelines(limit: int = 30):
    safe_limit = max(1, min(limit, 100))
    try:
        pipelines = _load_pipeline_rows(safe_limit)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail="Project Health CI history is unavailable.",
        ) from exc

    return {
        "count": len(pipelines),
        "items": pipelines,
    }


@router.get("/alerts")
def list_alerts():
    summary = project_health_summary()
    return {
        "count": len(summary["alerts"]),
        "items": summary["alerts"],
    }
