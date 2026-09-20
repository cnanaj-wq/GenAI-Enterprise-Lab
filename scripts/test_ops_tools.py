"""Manual smoke test for the Module 1 SQL tool layer.

Run from the repository root:
    python scripts/test_ops_tools.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import text

from apps.api.app.database import engine
from apps.api.app.tools.ops_tools import (
    check_dependencies,
    get_application,
    get_incident,
    get_jira_ticket,
    get_reload_history,
    get_reload_logs,
)


def dump(title: str, value: Any) -> None:
    print(f"\n{'=' * 72}")
    print(title)
    print("=" * 72)
    print(json.dumps(value, indent=2, default=str, ensure_ascii=False))


def discover_failed_reload() -> dict[str, Any]:
    sql = """
        SELECT
            a.application_name,
            r.application_id,
            r.reload_id,
            r.started_at
        FROM ops.reload_jobs AS r
        JOIN ops.applications AS a
          ON a.application_id = r.application_id
        WHERE r.status = 'FAILED'
        ORDER BY r.started_at DESC
        LIMIT 1;
    """

    with engine.connect() as connection:
        row = connection.execute(text(sql)).mappings().first()

    if row is None:
        raise RuntimeError("No FAILED reload found in the DEV dataset.")

    return dict(row)


def main() -> None:
    candidate = discover_failed_reload()
    dump("0. Candidate discovered for smoke test", candidate)

    application = get_application(candidate["application_name"])
    dump("1. get_application()", application)

    if application is None:
        raise RuntimeError("Application lookup failed.")

    failed_history = get_reload_history(
        application["application_id"],
        status="FAILED",
        limit=5,
    )
    dump("2. get_reload_history(status='FAILED')", failed_history)

    reload_id = candidate["reload_id"]

    logs = get_reload_logs(reload_id, limit=50)
    dump("3. get_reload_logs()", logs)

    incident = get_incident(reload_id)
    dump("4. get_incident()", incident)

    if incident is not None:
        jira = get_jira_ticket(incident["incident_id"])
        dump("5. get_jira_ticket()", jira)
    else:
        dump("5. get_jira_ticket()", "Skipped: no incident for this reload.")

    dependencies = check_dependencies(application["application_id"])
    dump("6. check_dependencies()", dependencies)

    print("\nSQL tool smoke test complete.")


if __name__ == "__main__":
    main()
