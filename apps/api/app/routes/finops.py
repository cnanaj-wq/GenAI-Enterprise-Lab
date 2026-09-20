"""GenAI FinOps / Usage & Cost analytics endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from apps.api.app.database import engine

router = APIRouter(prefix="/api/v1/finops", tags=["finops"])


def _base_from() -> str:
    return """
    FROM finops.usage_events e
    JOIN finops.users u ON u.user_id = e.user_id
    JOIN finops.teams t ON t.team_id = e.team_id
    JOIN finops.business_units bu ON bu.business_unit_id = e.business_unit_id
    JOIN finops.use_cases uc ON uc.use_case_id = e.use_case_id
    JOIN finops.models m ON m.model_id = e.model_id
    """


def _filters(
    business_unit: str | None,
    team: str | None,
    use_case: str | None,
    model: str | None,
) -> tuple[str, dict[str, Any]]:
    clauses: list[str] = []
    params: dict[str, Any] = {}

    if business_unit:
        clauses.append("bu.business_unit_name = :business_unit")
        params["business_unit"] = business_unit

    if team:
        clauses.append("t.team_name = :team")
        params["team"] = team

    if use_case:
        clauses.append("uc.use_case_name = :use_case")
        params["use_case"] = use_case

    if model:
        clauses.append("m.model_name = :model")
        params["model"] = model

    if not clauses:
        return "", params

    return " AND " + " AND ".join(clauses), params


@router.get("/options")
def options():
    try:
        with engine.connect() as connection:
            business_units = (
                connection.execute(
                    text(
                        """
                    SELECT business_unit_name
                    FROM finops.business_units
                    ORDER BY business_unit_name;
                    """
                    )
                )
                .scalars()
                .all()
            )

            teams = (
                connection.execute(
                    text(
                        """
                    SELECT team_name
                    FROM finops.teams
                    ORDER BY team_name;
                    """
                    )
                )
                .scalars()
                .all()
            )

            use_cases = (
                connection.execute(
                    text(
                        """
                    SELECT use_case_name
                    FROM finops.use_cases
                    ORDER BY use_case_name;
                    """
                    )
                )
                .scalars()
                .all()
            )

            models = (
                connection.execute(
                    text(
                        """
                    SELECT model_name
                    FROM finops.models
                    ORDER BY model_id;
                    """
                    )
                )
                .scalars()
                .all()
            )
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail="FinOps tables unavailable. Apply migration 006 and generate history.",
        ) from exc

    return {
        "business_units": business_units,
        "teams": teams,
        "use_cases": use_cases,
        "models": models,
    }


@router.get("/overview")
def overview(
    days: int = Query(30, ge=1, le=120),
    business_unit: str | None = None,
    team: str | None = None,
    use_case: str | None = None,
    model: str | None = None,
):
    now = datetime.now(timezone.utc)
    start_at = now - timedelta(days=days)

    filter_sql, filter_params = _filters(
        business_unit,
        team,
        use_case,
        model,
    )
    params = {"start_at": start_at, **filter_params}

    try:
        with engine.connect() as connection:
            kpis = (
                connection.execute(
                    text(
                        f"""
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
                    {_base_from()}
                    WHERE e.occurred_at >= :start_at
                    {filter_sql};
                    """
                    ),
                    params,
                )
                .mappings()
                .one()
            )

            time_series = (
                connection.execute(
                    text(
                        f"""
                    SELECT
                        DATE(e.occurred_at) AS usage_day,
                        COUNT(*) AS requests,
                        SUM(e.total_tokens) AS total_tokens,
                        SUM(e.estimated_cost_usd) AS cost_usd
                    {_base_from()}
                    WHERE e.occurred_at >= :start_at
                    {filter_sql}
                    GROUP BY DATE(e.occurred_at)
                    ORDER BY usage_day;
                    """
                    ),
                    params,
                )
                .mappings()
                .all()
            )

            by_use_case = (
                connection.execute(
                    text(
                        f"""
                    SELECT
                        uc.use_case_name AS name,
                        COUNT(*) AS requests,
                        SUM(e.total_tokens) AS total_tokens,
                        SUM(e.estimated_cost_usd) AS cost_usd,
                        AVG(e.estimated_cost_usd) AS cost_per_request,
                        AVG(e.latency_ms) AS avg_latency_ms
                    {_base_from()}
                    WHERE e.occurred_at >= :start_at
                    {filter_sql}
                    GROUP BY uc.use_case_name
                    ORDER BY cost_usd DESC;
                    """
                    ),
                    params,
                )
                .mappings()
                .all()
            )

            by_model = (
                connection.execute(
                    text(
                        f"""
                    SELECT
                        m.model_name AS name,
                        m.model_tier AS tier,
                        COUNT(*) AS requests,
                        SUM(e.total_tokens) AS total_tokens,
                        SUM(e.estimated_cost_usd) AS cost_usd
                    {_base_from()}
                    WHERE e.occurred_at >= :start_at
                    {filter_sql}
                    GROUP BY m.model_id, m.model_name, m.model_tier
                    ORDER BY m.model_id;
                    """
                    ),
                    params,
                )
                .mappings()
                .all()
            )

            by_business_unit = (
                connection.execute(
                    text(
                        f"""
                    SELECT
                        bu.business_unit_name AS name,
                        COUNT(*) AS requests,
                        COUNT(DISTINCT e.user_id) AS active_users,
                        SUM(e.total_tokens) AS total_tokens,
                        SUM(e.estimated_cost_usd) AS cost_usd
                    {_base_from()}
                    WHERE e.occurred_at >= :start_at
                    {filter_sql}
                    GROUP BY bu.business_unit_name
                    ORDER BY cost_usd DESC;
                    """
                    ),
                    params,
                )
                .mappings()
                .all()
            )

            top_users = (
                connection.execute(
                    text(
                        f"""
                    SELECT
                        u.display_name AS user_name,
                        t.team_name,
                        bu.business_unit_name,
                        COUNT(*) AS requests,
                        SUM(e.total_tokens) AS total_tokens,
                        SUM(e.estimated_cost_usd) AS cost_usd
                    {_base_from()}
                    WHERE e.occurred_at >= :start_at
                    {filter_sql}
                    GROUP BY
                        u.user_id,
                        u.display_name,
                        t.team_name,
                        bu.business_unit_name
                    ORDER BY cost_usd DESC
                    LIMIT 10;
                    """
                    ),
                    params,
                )
                .mappings()
                .all()
            )

            # Scope-aware budget target.
            if team:
                budget_rows = (
                    connection.execute(
                        text(
                            """
                        SELECT
                            t.team_name AS name,
                            t.monthly_budget_usd AS budget_usd,
                            COALESCE(SUM(e.estimated_cost_usd), 0) AS spend_usd
                        FROM finops.teams t
                        LEFT JOIN finops.usage_events e
                          ON e.team_id = t.team_id
                         AND e.occurred_at >= date_trunc('month', NOW())
                        WHERE t.team_name = :team
                        GROUP BY t.team_id, t.team_name, t.monthly_budget_usd;
                        """
                        ),
                        {"team": team},
                    )
                    .mappings()
                    .all()
                )
            elif business_unit:
                budget_rows = (
                    connection.execute(
                        text(
                            """
                        SELECT
                            bu.business_unit_name AS name,
                            bu.monthly_budget_usd AS budget_usd,
                            COALESCE(SUM(e.estimated_cost_usd), 0) AS spend_usd
                        FROM finops.business_units bu
                        LEFT JOIN finops.usage_events e
                          ON e.business_unit_id = bu.business_unit_id
                         AND e.occurred_at >= date_trunc('month', NOW())
                        WHERE bu.business_unit_name = :business_unit
                        GROUP BY
                            bu.business_unit_id,
                            bu.business_unit_name,
                            bu.monthly_budget_usd;
                        """
                        ),
                        {"business_unit": business_unit},
                    )
                    .mappings()
                    .all()
                )
            elif use_case:
                budget_rows = (
                    connection.execute(
                        text(
                            """
                        SELECT
                            uc.use_case_name AS name,
                            uc.monthly_budget_usd AS budget_usd,
                            COALESCE(SUM(e.estimated_cost_usd), 0) AS spend_usd
                        FROM finops.use_cases uc
                        LEFT JOIN finops.usage_events e
                          ON e.use_case_id = uc.use_case_id
                         AND e.occurred_at >= date_trunc('month', NOW())
                        WHERE uc.use_case_name = :use_case
                        GROUP BY
                            uc.use_case_id,
                            uc.use_case_name,
                            uc.monthly_budget_usd;
                        """
                        ),
                        {"use_case": use_case},
                    )
                    .mappings()
                    .all()
                )
            else:
                budget_rows = (
                    connection.execute(
                        text(
                            """
                        SELECT
                            bu.business_unit_name AS name,
                            bu.monthly_budget_usd AS budget_usd,
                            COALESCE(SUM(e.estimated_cost_usd), 0) AS spend_usd
                        FROM finops.business_units bu
                        LEFT JOIN finops.usage_events e
                          ON e.business_unit_id = bu.business_unit_id
                         AND e.occurred_at >= date_trunc('month', NOW())
                        GROUP BY
                            bu.business_unit_id,
                            bu.business_unit_name,
                            bu.monthly_budget_usd
                        ORDER BY spend_usd DESC;
                        """
                        )
                    )
                    .mappings()
                    .all()
                )

            # Scope-aware anomaly signal.
            scope_signal = (
                connection.execute(
                    text(
                        f"""
                    SELECT
                        SUM(
                            CASE
                                WHEN e.occurred_at >= NOW() - INTERVAL '7 days'
                                THEN e.estimated_cost_usd
                                ELSE 0
                            END
                        ) AS recent_cost,
                        SUM(
                            CASE
                                WHEN e.occurred_at >= NOW() - INTERVAL '14 days'
                                 AND e.occurred_at < NOW() - INTERVAL '7 days'
                                THEN e.estimated_cost_usd
                                ELSE 0
                            END
                        ) AS previous_cost,
                        AVG(
                            CASE
                                WHEN e.occurred_at >= NOW() - INTERVAL '7 days'
                                THEN e.retry_count::numeric
                            END
                        ) AS recent_retry_avg,
                        100.0 * SUM(
                            CASE
                                WHEN e.occurred_at >= NOW() - INTERVAL '14 days'
                                 AND m.model_tier = 'PREMIUM'
                                THEN 1
                                ELSE 0
                            END
                        ) / NULLIF(
                            SUM(
                                CASE
                                    WHEN e.occurred_at >= NOW() - INTERVAL '14 days'
                                    THEN 1
                                    ELSE 0
                                END
                            ),
                            0
                        ) AS premium_pct
                    {_base_from()}
                    WHERE e.occurred_at >= NOW() - INTERVAL '14 days'
                    {filter_sql};
                    """
                    ),
                    filter_params,
                )
                .mappings()
                .one()
            )

    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail="FinOps analytics unavailable.",
        ) from exc

    alerts: list[dict[str, Any]] = []

    for row in budget_rows:
        budget = float(row["budget_usd"] or 0)
        spend = float(row["spend_usd"] or 0)
        pct = 100.0 * spend / budget if budget else 0.0

        if pct >= 75.0:
            severity = "CRITICAL" if pct >= 90.0 else "WARNING"
            code = (
                "BUDGET_EXCEEDED" if pct >= 100.0 else ("BUDGET_90" if pct >= 90.0 else "BUDGET_75")
            )
            alerts.append(
                {
                    "severity": severity,
                    "code": code,
                    "title": f"{row['name']} — budget mensuel",
                    "message": f"{pct:.1f} % consommé (${spend:.2f} / ${budget:.2f}).",
                }
            )

    scope_parts = [
        business_unit or "",
        team or "",
        use_case or "",
        model or "",
    ]
    scope_label = " · ".join(part for part in scope_parts if part) or "Entreprise"

    recent = float(scope_signal["recent_cost"] or 0)
    previous = float(scope_signal["previous_cost"] or 0)
    if previous > 0:
        growth = 100.0 * (recent - previous) / previous
        if growth >= 60.0:
            alerts.append(
                {
                    "severity": "WARNING",
                    "code": "COST_SURGE",
                    "title": f"{scope_label} — hausse de coût",
                    "message": f"+{growth:.1f} % sur 7 jours vs période précédente.",
                }
            )

    retry_avg = float(scope_signal["recent_retry_avg"] or 0)
    if retry_avg >= 0.10:
        alerts.append(
            {
                "severity": "WARNING",
                "code": "RETRY_SPIKE",
                "title": f"{scope_label} — retries élevés",
                "message": f"Moyenne récente : {retry_avg:.2f} retry/request.",
            }
        )

    premium_pct = float(scope_signal["premium_pct"] or 0)
    if premium_pct >= 35.0:
        alerts.append(
            {
                "severity": "WARNING",
                "code": "PREMIUM_OVERUSE",
                "title": f"{scope_label} — modèle premium",
                "message": f"{premium_pct:.1f} % des requêtes utilisent le modèle premium.",
            }
        )

    return {
        "generated_at": now,
        "days": days,
        "kpis": dict(kpis),
        "time_series": [{**dict(row), "day": dict(row).get("usage_day")} for row in time_series],
        "by_use_case": [dict(row) for row in by_use_case],
        "by_model": [dict(row) for row in by_model],
        "by_business_unit": [dict(row) for row in by_business_unit],
        "top_users": [dict(row) for row in top_users],
        "budgets": [dict(row) for row in budget_rows],
        "alerts": alerts,
    }
