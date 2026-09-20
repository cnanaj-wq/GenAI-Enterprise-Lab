"""Deterministic optimization recommendations for GenAI FinOps."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Query
from sqlalchemy import text

from apps.api.app.database import engine

router = APIRouter(prefix="/api/v1/optimize", tags=["optimize"])


@dataclass
class Recommendation:
    rule_id: str
    category: str
    priority: str
    title: str
    observation: str
    diagnostic: str
    recommendation: str
    estimated_impact: str
    estimated_savings_usd: float
    confidence: str
    metric_name: str
    metric_value: float
    threshold: float


def _priority(value: float, medium: float, high: float, inverse: bool = False) -> str:
    if inverse:
        if value <= high:
            return "HIGH"
        if value <= medium:
            return "MEDIUM"
        return "LOW"

    if value >= high:
        return "HIGH"
    if value >= medium:
        return "MEDIUM"
    return "LOW"


def build_recommendations(
    metrics: dict[str, float],
    model_rows: list[dict[str, Any]],
) -> list[Recommendation]:
    """Build deterministic recommendations from measurable thresholds."""

    recommendations: list[Recommendation] = []

    cost = float(metrics.get("cost_usd", 0.0))
    input_tokens = float(metrics.get("input_tokens", 0.0))
    output_tokens = float(metrics.get("output_tokens", 0.0))
    requests = max(float(metrics.get("requests", 0.0)), 1.0)
    retry_rate = float(metrics.get("retry_rate_pct", 0.0))
    success_rate = float(metrics.get("success_rate_pct", 100.0))
    avg_latency = float(metrics.get("avg_latency_ms", 0.0))
    cost_per_request = float(metrics.get("cost_per_request", 0.0))

    total_tokens = input_tokens + output_tokens
    input_share = (input_tokens / total_tokens * 100.0) if total_tokens else 0.0
    avg_input_per_request = input_tokens / requests

    if input_share >= 82.0 and avg_input_per_request >= 3500:
        reduction = 0.15
        estimated_savings = cost * reduction * (input_tokens / total_tokens if total_tokens else 0)
        recommendations.append(
            Recommendation(
                rule_id="CTX-001",
                category="CONTEXT",
                priority=_priority(input_share, 82.0, 90.0),
                title="Réduire le contexte envoyé au LLM",
                observation=(
                    f"{input_share:.1f}% des tokens sont des tokens d'entrée "
                    f"({avg_input_per_request:,.0f} tokens/requête)."
                ),
                diagnostic=(
                    "Le coût est dominé par le contexte. Une partie du contexte peut être "
                    "redondante, trop large ou systématiquement envoyée même lorsqu'elle n'est "
                    "pas utile à la requête."
                ),
                recommendation=(
                    "Limiter le contexte aux passages utiles, réduire les instructions répétées "
                    "et appliquer une sélection RAG plus stricte."
                ),
                estimated_impact=(
                    "Simulation prudente : -15% de tokens d'entrée sur le scope sélectionné."
                ),
                estimated_savings_usd=round(estimated_savings, 4),
                confidence="HIGH",
                metric_name="input_token_share_pct",
                metric_value=round(input_share, 2),
                threshold=82.0,
            )
        )

    premium_rows = [
        row
        for row in model_rows
        if str(row.get("model_tier", "")).upper() == "PREMIUM"
    ]
    standard_rows = [
        row
        for row in model_rows
        if str(row.get("model_tier", "")).upper() == "STANDARD"
    ]

    premium_requests = sum(float(row.get("requests", 0)) for row in premium_rows)
    premium_share = premium_requests / requests * 100.0

    if premium_share >= 30.0 and premium_rows and standard_rows:
        premium_cost = sum(float(row.get("cost_usd", 0.0)) for row in premium_rows)
        premium_req = max(sum(float(row.get("requests", 0.0)) for row in premium_rows), 1.0)
        standard_cost = sum(float(row.get("cost_usd", 0.0)) for row in standard_rows)
        standard_req = max(sum(float(row.get("requests", 0.0)) for row in standard_rows), 1.0)

        premium_unit = premium_cost / premium_req
        standard_unit = standard_cost / standard_req
        shift_requests = premium_req * 0.20
        estimated_savings = max((premium_unit - standard_unit) * shift_requests, 0.0)

        recommendations.append(
            Recommendation(
                rule_id="ROUTE-001",
                category="MODEL ROUTING",
                priority=_priority(premium_share, 30.0, 45.0),
                title="Router une partie du trafic premium vers le modèle standard",
                observation=(
                    f"{premium_share:.1f}% des requêtes utilisent un modèle PREMIUM."
                ),
                diagnostic=(
                    "Une part importante du trafic utilise le niveau de modèle le plus coûteux. "
                    "Toutes les requêtes n'exigent probablement pas la même capacité."
                ),
                recommendation=(
                    "Ajouter une règle de model routing déterministe : requêtes simples vers "
                    "STANDARD, cas complexes ou sensibles vers PREMIUM."
                ),
                estimated_impact=(
                    "Simulation : basculer 20% du trafic PREMIUM vers STANDARD, "
                    "sans modifier les requêtes restantes."
                ),
                estimated_savings_usd=round(estimated_savings, 4),
                confidence="MEDIUM",
                metric_name="premium_request_share_pct",
                metric_value=round(premium_share, 2),
                threshold=30.0,
            )
        )

    if retry_rate >= 5.0:
        recommendations.append(
            Recommendation(
                rule_id="REL-001",
                category="RELIABILITY",
                priority=_priority(retry_rate, 5.0, 8.0),
                title="Réduire les retries",
                observation=f"Le retry rate atteint {retry_rate:.1f}%.",
                diagnostic=(
                    "Les retries augmentent la charge, la latence et peuvent générer des appels "
                    "LLM/MCP supplémentaires."
                ),
                recommendation=(
                    "Segmenter les retries par cause : timeout MCP, erreur provider, rate limit, "
                    "réponse invalide. Réessayer uniquement les erreurs réellement transitoires."
                ),
                estimated_impact=(
                    "Objectif opérationnel : ramener le retry rate sous 5%. "
                    "Le gain financier n'est pas chiffré ici car le dataset ne distingue pas "
                    "le coût exact de chaque tentative."
                ),
                estimated_savings_usd=0.0,
                confidence="HIGH",
                metric_name="retry_rate_pct",
                metric_value=round(retry_rate, 2),
                threshold=5.0,
            )
        )

    if avg_latency >= 7000.0:
        recommendations.append(
            Recommendation(
                rule_id="LAT-001",
                category="LATENCY",
                priority=_priority(avg_latency, 7000.0, 10000.0),
                title="Réduire la latence moyenne",
                observation=f"La latence moyenne est de {avg_latency / 1000:.2f} s.",
                diagnostic=(
                    "La latence dépasse le seuil de confort retenu pour le cockpit. "
                    "Elle peut provenir du LLM, de MCP, des appels séquentiels ou d'un contexte trop lourd."
                ),
                recommendation=(
                    "Analyser les spans LLM/MCP, paralléliser les appels indépendants et réduire "
                    "le contexte avant d'envisager un modèle plus rapide."
                ),
                estimated_impact=(
                    "Cible de travail : -15% de latence moyenne avant changement d'architecture."
                ),
                estimated_savings_usd=0.0,
                confidence="MEDIUM",
                metric_name="avg_latency_ms",
                metric_value=round(avg_latency, 2),
                threshold=7000.0,
            )
        )

    if success_rate < 97.0:
        recommendations.append(
            Recommendation(
                rule_id="QUAL-001",
                category="QUALITY",
                priority=_priority(success_rate, 97.0, 94.0, inverse=True),
                title="Stabiliser le taux de succès",
                observation=f"Le success rate est de {success_rate:.1f}%.",
                diagnostic=(
                    "Le scope présente un niveau d'échec supérieur au seuil de qualité opérationnelle."
                ),
                recommendation=(
                    "Corréler les échecs avec les traces et classer les causes : provider, MCP, "
                    "validation, timeout ou données manquantes."
                ),
                estimated_impact="Cible : success rate >= 97%.",
                estimated_savings_usd=0.0,
                confidence="HIGH",
                metric_name="success_rate_pct",
                metric_value=round(success_rate, 2),
                threshold=97.0,
            )
        )

    if cost_per_request >= 0.02:
        estimated_savings = cost * 0.10
        recommendations.append(
            Recommendation(
                rule_id="COST-001",
                category="COST",
                priority=_priority(cost_per_request, 0.02, 0.05),
                title="Réduire le coût moyen par requête",
                observation=f"Le coût moyen atteint ${cost_per_request:.4f}/requête.",
                diagnostic=(
                    "Le coût unitaire est suffisamment élevé pour justifier une optimisation "
                    "du couple modèle + contexte + longueur de réponse."
                ),
                recommendation=(
                    "Tester trois variantes mesurées : contexte réduit, routage vers un modèle "
                    "moins coûteux et limite de sortie adaptée au use case."
                ),
                estimated_impact=(
                    "Simulation conservative : -10% du coût total si le coût/requête baisse "
                    "sans baisse de qualité."
                ),
                estimated_savings_usd=round(estimated_savings, 4),
                confidence="MEDIUM",
                metric_name="cost_per_request",
                metric_value=round(cost_per_request, 6),
                threshold=0.02,
            )
        )

    priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    recommendations.sort(
        key=lambda item: (
            priority_order.get(item.priority, 9),
            -item.estimated_savings_usd,
            item.rule_id,
        )
    )
    return recommendations


def _scope_conditions(
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

    where = ""
    if clauses:
        where = " AND " + " AND ".join(clauses)

    return where, params


@router.get("/recommendations")
def recommendations(
    days: int = Query(default=30, ge=1, le=120),
    business_unit: str | None = None,
    team: str | None = None,
    use_case: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    start_at = datetime.now(timezone.utc) - timedelta(days=days)
    where, params = _scope_conditions(business_unit, team, use_case, model)
    params["start_at"] = start_at

    base_join = """
        FROM finops.usage_events e
        JOIN finops.users u ON u.user_id = e.user_id
        JOIN finops.teams t ON t.team_id = e.team_id
        JOIN finops.business_units bu ON bu.business_unit_id = e.business_unit_id
        JOIN finops.use_cases uc ON uc.use_case_id = e.use_case_id
        JOIN finops.models m ON m.model_id = e.model_id
        WHERE e.occurred_at >= :start_at
    """

    metrics_sql = text(
        f"""
        SELECT
            COALESCE(SUM(e.estimated_cost_usd), 0)::float AS cost_usd,
            COALESCE(SUM(e.input_tokens), 0)::float AS input_tokens,
            COALESCE(SUM(e.output_tokens), 0)::float AS output_tokens,
            COUNT(*)::float AS requests,
            COALESCE(AVG(e.latency_ms), 0)::float AS avg_latency_ms,
            COALESCE(AVG(e.retry_count), 0)::float * 100.0 AS retry_rate_pct,
            COALESCE(AVG(CASE WHEN e.success THEN 1.0 ELSE 0.0 END), 0)::float
                * 100.0 AS success_rate_pct,
            CASE
                WHEN COUNT(*) = 0 THEN 0
                ELSE COALESCE(SUM(e.estimated_cost_usd), 0)::float / COUNT(*)
            END AS cost_per_request
        {base_join}
        {where}
        """
    )

    model_sql = text(
        f"""
        SELECT
            m.model_name,
            m.model_tier,
            COUNT(*)::float AS requests,
            COALESCE(SUM(e.estimated_cost_usd), 0)::float AS cost_usd,
            COALESCE(SUM(e.input_tokens), 0)::float AS input_tokens,
            COALESCE(SUM(e.output_tokens), 0)::float AS output_tokens
        {base_join}
        {where}
        GROUP BY m.model_name, m.model_tier
        ORDER BY cost_usd DESC
        """
    )

    with engine.connect() as connection:
        metrics_row = connection.execute(metrics_sql, params).mappings().one()
        model_rows = list(connection.execute(model_sql, params).mappings())

    metrics = {key: float(value or 0) for key, value in dict(metrics_row).items()}
    models = [dict(row) for row in model_rows]
    recs = build_recommendations(metrics, models)

    total_savings = round(sum(item.estimated_savings_usd for item in recs), 4)
    current_cost = round(metrics["cost_usd"], 4)
    projected_cost = round(max(current_cost - total_savings, 0.0), 4)
    savings_pct = round((total_savings / current_cost * 100.0) if current_cost else 0.0, 2)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": {
            "days": days,
            "business_unit": business_unit,
            "team": team,
            "use_case": use_case,
            "model": model,
        },
        "metrics": metrics,
        "summary": {
            "recommendation_count": len(recs),
            "current_cost_usd": current_cost,
            "estimated_savings_usd": total_savings,
            "projected_cost_usd": projected_cost,
            "estimated_savings_pct": savings_pct,
        },
        "recommendations": [asdict(item) for item in recs],
        "methodology": {
            "type": "DETERMINISTIC_RULES",
            "llm_used": False,
            "automatic_changes": False,
            "note": (
                "Les impacts sont des simulations basées sur des hypothèses explicites. "
                "Aucune optimisation n'est appliquée automatiquement."
            ),
        },
    }
