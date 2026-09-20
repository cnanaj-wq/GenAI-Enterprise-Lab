from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.api.app.database import engine

start_at = datetime.now(timezone.utc) - timedelta(days=120)

queries = [
    (
        "KPI",
        """
        SELECT
            COUNT(*) AS requests,
            COUNT(DISTINCT e.user_id) AS active_users,
            COALESCE(SUM(e.input_tokens), 0) AS input_tokens,
            COALESCE(SUM(e.output_tokens), 0) AS output_tokens,
            COALESCE(SUM(e.total_tokens), 0) AS total_tokens,
            COALESCE(SUM(e.estimated_cost_usd), 0) AS cost_usd,
            COALESCE(AVG(e.estimated_cost_usd), 0) AS cost_per_request,
            COALESCE(AVG(e.total_tokens), 0) AS tokens_per_request,
            COALESCE(AVG(e.latency_ms), 0) AS avg_latency_ms,
            COALESCE(
                100.0 * SUM(CASE WHEN e.success THEN 1 ELSE 0 END)
                / NULLIF(COUNT(*), 0),
                0
            ) AS success_rate,
            COALESCE(
                100.0 * SUM(CASE WHEN e.retry_count > 0 THEN 1 ELSE 0 END)
                / NULLIF(COUNT(*), 0),
                0
            ) AS retry_rate
        FROM finops.usage_events e
        JOIN finops.users u ON u.user_id = e.user_id
        JOIN finops.teams t ON t.team_id = e.team_id
        JOIN finops.business_units bu ON bu.business_unit_id = e.business_unit_id
        JOIN finops.use_cases uc ON uc.use_case_id = e.use_case_id
        JOIN finops.models m ON m.model_id = e.model_id
        WHERE e.occurred_at >= :start_at
        """,
    ),
    (
        "TIME_SERIES",
        """
        SELECT
            DATE(e.occurred_at) AS day,
            COUNT(*) AS requests,
            SUM(e.total_tokens) AS total_tokens,
            SUM(e.estimated_cost_usd) AS cost_usd
        FROM finops.usage_events e
        JOIN finops.users u ON u.user_id = e.user_id
        JOIN finops.teams t ON t.team_id = e.team_id
        JOIN finops.business_units bu ON bu.business_unit_id = e.business_unit_id
        JOIN finops.use_cases uc ON uc.use_case_id = e.use_case_id
        JOIN finops.models m ON m.model_id = e.model_id
        WHERE e.occurred_at >= :start_at
        GROUP BY DATE(e.occurred_at)
        ORDER BY day
        """,
    ),
    (
        "BY_USE_CASE",
        """
        SELECT
            uc.use_case_name AS name,
            COUNT(*) AS requests,
            SUM(e.total_tokens) AS total_tokens,
            SUM(e.estimated_cost_usd) AS cost_usd,
            AVG(e.estimated_cost_usd) AS cost_per_request,
            AVG(e.latency_ms) AS avg_latency_ms
        FROM finops.usage_events e
        JOIN finops.users u ON u.user_id = e.user_id
        JOIN finops.teams t ON t.team_id = e.team_id
        JOIN finops.business_units bu ON bu.business_unit_id = e.business_unit_id
        JOIN finops.use_cases uc ON uc.use_case_id = e.use_case_id
        JOIN finops.models m ON m.model_id = e.model_id
        WHERE e.occurred_at >= :start_at
        GROUP BY uc.use_case_name
        ORDER BY cost_usd DESC
        """,
    ),
    (
        "BY_MODEL",
        """
        SELECT
            m.model_name AS name,
            m.model_tier AS tier,
            COUNT(*) AS requests,
            SUM(e.total_tokens) AS total_tokens,
            SUM(e.estimated_cost_usd) AS cost_usd
        FROM finops.usage_events e
        JOIN finops.users u ON u.user_id = e.user_id
        JOIN finops.teams t ON t.team_id = e.team_id
        JOIN finops.business_units bu ON bu.business_unit_id = e.business_unit_id
        JOIN finops.use_cases uc ON uc.use_case_id = e.use_case_id
        JOIN finops.models m ON m.model_id = e.model_id
        WHERE e.occurred_at >= :start_at
        GROUP BY m.model_name, m.model_tier, m.model_id
        ORDER BY m.model_id
        """,
    ),
    (
        "BY_BU",
        """
        SELECT
            bu.business_unit_name AS name,
            COUNT(*) AS requests,
            COUNT(DISTINCT e.user_id) AS active_users,
            SUM(e.total_tokens) AS total_tokens,
            SUM(e.estimated_cost_usd) AS cost_usd
        FROM finops.usage_events e
        JOIN finops.users u ON u.user_id = e.user_id
        JOIN finops.teams t ON t.team_id = e.team_id
        JOIN finops.business_units bu ON bu.business_unit_id = e.business_unit_id
        JOIN finops.use_cases uc ON uc.use_case_id = e.use_case_id
        JOIN finops.models m ON m.model_id = e.model_id
        WHERE e.occurred_at >= :start_at
        GROUP BY bu.business_unit_name
        ORDER BY cost_usd DESC
        """,
    ),
    (
        "TOP_USERS",
        """
        SELECT
            u.display_name AS user_name,
            t.team_name,
            bu.business_unit_name,
            COUNT(*) AS requests,
            SUM(e.total_tokens) AS total_tokens,
            SUM(e.estimated_cost_usd) AS cost_usd
        FROM finops.usage_events e
        JOIN finops.users u ON u.user_id = e.user_id
        JOIN finops.teams t ON t.team_id = e.team_id
        JOIN finops.business_units bu ON bu.business_unit_id = e.business_unit_id
        JOIN finops.use_cases uc ON uc.use_case_id = e.use_case_id
        JOIN finops.models m ON m.model_id = e.model_id
        WHERE e.occurred_at >= :start_at
        GROUP BY u.user_id, u.display_name, t.team_name, bu.business_unit_name
        ORDER BY cost_usd DESC
        LIMIT 10
        """,
    ),
    (
        "BUDGETS",
        """
        SELECT
            bu.business_unit_name AS name,
            bu.monthly_budget_usd AS budget_usd,
            COALESCE(SUM(e.estimated_cost_usd), 0) AS spend_usd
        FROM finops.business_units bu
        LEFT JOIN finops.usage_events e
          ON e.business_unit_id = bu.business_unit_id
         AND e.occurred_at >= date_trunc('month', NOW())
        GROUP BY bu.business_unit_id, bu.business_unit_name, bu.monthly_budget_usd
        ORDER BY spend_usd DESC
        """,
    ),
    (
        "ANOMALIES",
        """
        WITH team_cost AS (
            SELECT
                t.team_name,
                SUM(
                    CASE
                        WHEN e.occurred_at >= NOW() - INTERVAL '7 days'
                        THEN e.estimated_cost_usd ELSE 0
                    END
                ) AS recent_cost,
                SUM(
                    CASE
                        WHEN e.occurred_at >= NOW() - INTERVAL '14 days'
                         AND e.occurred_at < NOW() - INTERVAL '7 days'
                        THEN e.estimated_cost_usd ELSE 0
                    END
                ) AS previous_cost,
                AVG(
                    CASE
                        WHEN e.occurred_at >= NOW() - INTERVAL '7 days'
                        THEN e.retry_count::numeric
                    END
                ) AS recent_retry_avg
            FROM finops.teams t
            LEFT JOIN finops.usage_events e ON e.team_id = t.team_id
            GROUP BY t.team_name
        )
        SELECT * FROM team_cost ORDER BY recent_cost DESC
        """,
    ),
    (
        "PREMIUM_OVERUSE",
        """
        SELECT
            t.team_name,
            100.0 * SUM(CASE WHEN m.model_tier = 'PREMIUM' THEN 1 ELSE 0 END)
            / NULLIF(COUNT(*), 0) AS premium_pct
        FROM finops.usage_events e
        JOIN finops.teams t ON t.team_id = e.team_id
        JOIN finops.models m ON m.model_id = e.model_id
        WHERE e.occurred_at >= NOW() - INTERVAL '14 days'
        GROUP BY t.team_name
        ORDER BY premium_pct DESC
        """,
    ),
]

with engine.connect() as conn:
    for name, sql in queries:
        print(f"\n{name}")
        print("=" * 72)
        try:
            params = {"start_at": start_at} if ":start_at" in sql else {}
            rows = conn.execute(text(sql), params).fetchall()
            print(f"PASS — rows={len(rows)}")
        except Exception as exc:
            print("FAIL")
            print(type(exc).__name__)
            print(exc)
            break
