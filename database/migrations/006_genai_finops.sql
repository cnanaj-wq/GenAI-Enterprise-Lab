BEGIN;

CREATE SCHEMA IF NOT EXISTS finops;

CREATE TABLE IF NOT EXISTS finops.business_units (
    business_unit_id SMALLSERIAL PRIMARY KEY,
    business_unit_name TEXT NOT NULL UNIQUE,
    monthly_budget_usd NUMERIC(12,2) NOT NULL CHECK (monthly_budget_usd > 0)
);

CREATE TABLE IF NOT EXISTS finops.teams (
    team_id SMALLSERIAL PRIMARY KEY,
    business_unit_id SMALLINT NOT NULL REFERENCES finops.business_units(business_unit_id),
    team_name TEXT NOT NULL UNIQUE,
    monthly_budget_usd NUMERIC(12,2) NOT NULL CHECK (monthly_budget_usd > 0)
);

CREATE TABLE IF NOT EXISTS finops.users (
    user_id INTEGER PRIMARY KEY,
    team_id SMALLINT NOT NULL REFERENCES finops.teams(team_id),
    display_name TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS finops.use_cases (
    use_case_id SMALLSERIAL PRIMARY KEY,
    use_case_name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL,
    monthly_budget_usd NUMERIC(12,2) NOT NULL CHECK (monthly_budget_usd > 0)
);

CREATE TABLE IF NOT EXISTS finops.models (
    model_id SMALLSERIAL PRIMARY KEY,
    model_name TEXT NOT NULL UNIQUE,
    input_cost_per_million NUMERIC(12,6) NOT NULL,
    output_cost_per_million NUMERIC(12,6) NOT NULL,
    model_tier TEXT NOT NULL CHECK (model_tier IN ('ECONOMY','STANDARD','PREMIUM'))
);

CREATE TABLE IF NOT EXISTS finops.usage_events (
    usage_event_id BIGSERIAL PRIMARY KEY,
    occurred_at TIMESTAMPTZ NOT NULL,
    user_id INTEGER NOT NULL REFERENCES finops.users(user_id),
    team_id SMALLINT NOT NULL REFERENCES finops.teams(team_id),
    business_unit_id SMALLINT NOT NULL REFERENCES finops.business_units(business_unit_id),
    use_case_id SMALLINT NOT NULL REFERENCES finops.use_cases(use_case_id),
    model_id SMALLINT NOT NULL REFERENCES finops.models(model_id),
    input_tokens INTEGER NOT NULL CHECK (input_tokens >= 0),
    output_tokens INTEGER NOT NULL CHECK (output_tokens >= 0),
    total_tokens INTEGER GENERATED ALWAYS AS (input_tokens + output_tokens) STORED,
    latency_ms INTEGER NOT NULL CHECK (latency_ms >= 0),
    retry_count SMALLINT NOT NULL DEFAULT 0 CHECK (retry_count >= 0),
    success BOOLEAN NOT NULL,
    estimated_cost_usd NUMERIC(14,8) NOT NULL CHECK (estimated_cost_usd >= 0)
);

CREATE INDEX IF NOT EXISTS idx_finops_usage_time ON finops.usage_events (occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_finops_usage_bu_time ON finops.usage_events (business_unit_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_finops_usage_team_time ON finops.usage_events (team_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_finops_usage_use_case_time ON finops.usage_events (use_case_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_finops_usage_model_time ON finops.usage_events (model_id, occurred_at DESC);

COMMIT;
