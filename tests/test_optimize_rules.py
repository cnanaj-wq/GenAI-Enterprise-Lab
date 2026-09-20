from apps.api.app.routes.optimize import build_recommendations


def test_context_rule_triggers() -> None:
    metrics = {
        "cost_usd": 100.0,
        "input_tokens": 900_000.0,
        "output_tokens": 100_000.0,
        "requests": 100.0,
        "avg_latency_ms": 5000.0,
        "retry_rate_pct": 2.0,
        "success_rate_pct": 99.0,
        "cost_per_request": 0.01,
    }

    recs = build_recommendations(metrics, [])
    ids = {item.rule_id for item in recs}
    assert "CTX-001" in ids


def test_model_routing_rule_triggers() -> None:
    metrics = {
        "cost_usd": 200.0,
        "input_tokens": 100_000.0,
        "output_tokens": 100_000.0,
        "requests": 100.0,
        "avg_latency_ms": 5000.0,
        "retry_rate_pct": 2.0,
        "success_rate_pct": 99.0,
        "cost_per_request": 0.01,
    }
    models = [
        {
            "model_name": "premium",
            "model_tier": "PREMIUM",
            "requests": 50.0,
            "cost_usd": 150.0,
        },
        {
            "model_name": "standard",
            "model_tier": "STANDARD",
            "requests": 50.0,
            "cost_usd": 50.0,
        },
    ]

    recs = build_recommendations(metrics, models)
    route = next(item for item in recs if item.rule_id == "ROUTE-001")
    assert route.estimated_savings_usd > 0
