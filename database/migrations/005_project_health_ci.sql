BEGIN;

CREATE SCHEMA IF NOT EXISTS delivery;

CREATE TABLE IF NOT EXISTS delivery.ci_pipeline_runs (
    pipeline_id UUID PRIMARY KEY,
    source_type TEXT NOT NULL CHECK (source_type IN ('SYNTHETIC', 'REAL_LOCAL', 'GITHUB_ACTIONS')),
    branch TEXT NOT NULL,
    commit_sha TEXT NOT NULL,
    commit_message TEXT NOT NULL,
    triggered_by TEXT NOT NULL,
    trigger_type TEXT NOT NULL CHECK (trigger_type IN ('PUSH', 'PULL_REQUEST', 'MANUAL')),
    push_at TIMESTAMPTZ,
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ NOT NULL,
    duration_ms INTEGER NOT NULL CHECK (duration_ms >= 0),
    status TEXT NOT NULL CHECK (status IN ('PASS', 'FAIL', 'WARNING')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS delivery.ci_pipeline_checks (
    check_id BIGSERIAL PRIMARY KEY,
    pipeline_id UUID NOT NULL REFERENCES delivery.ci_pipeline_runs(pipeline_id) ON DELETE CASCADE,
    check_name TEXT NOT NULL CHECK (check_name IN ('RUFF', 'PYTEST', 'ESLINT', 'NEXTJS_BUILD')),
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ NOT NULL,
    duration_ms INTEGER NOT NULL CHECK (duration_ms >= 0),
    status TEXT NOT NULL CHECK (status IN ('PASS', 'FAIL', 'WARNING')),
    error_message TEXT,
    UNIQUE (pipeline_id, check_name)
);

CREATE INDEX IF NOT EXISTS idx_ci_pipeline_runs_started_at
    ON delivery.ci_pipeline_runs (started_at DESC);

CREATE INDEX IF NOT EXISTS idx_ci_pipeline_runs_status
    ON delivery.ci_pipeline_runs (status, started_at DESC);

CREATE INDEX IF NOT EXISTS idx_ci_pipeline_checks_pipeline
    ON delivery.ci_pipeline_checks (pipeline_id, check_name);

COMMIT;
