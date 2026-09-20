-- GenAI Enterprise Lab
-- Module 1 — Agentic AI & MCP
-- Operations schema for the AI Ops Investigator
--
-- Target benchmark volume:
--   applications              150
--   data_sources               80
--   reload_jobs           600,000
--   reload_logs        10,000,000+
--   incidents              45,000
--   incident_events       180,000
--   jira_tickets           35,000
--   application_dependencies 2,000

BEGIN;

CREATE SCHEMA IF NOT EXISTS ops;

-- ============================================================
-- 1. Applications
-- ============================================================

CREATE TABLE IF NOT EXISTS ops.applications (
    application_id      integer PRIMARY KEY,
    application_name    text NOT NULL UNIQUE,
    domain              text NOT NULL,
    business_owner      text NOT NULL,
    technical_owner     text NOT NULL,
    criticality         text NOT NULL
                        CHECK (criticality IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    sla_time            time NOT NULL,
    sla_timezone        text NOT NULL DEFAULT 'Europe/Paris',
    active              boolean NOT NULL DEFAULT true,
    created_at          timestamptz NOT NULL,
    updated_at          timestamptz NOT NULL
);

COMMENT ON TABLE ops.applications IS
'BI / analytics applications supervised by the AI Ops Investigator.';


-- ============================================================
-- 2. Data sources
-- ============================================================

CREATE TABLE IF NOT EXISTS ops.data_sources (
    data_source_id      integer PRIMARY KEY,
    data_source_name    text NOT NULL UNIQUE,
    source_type         text NOT NULL
                        CHECK (
                            source_type IN (
                                'POSTGRESQL',
                                'SQLSERVER',
                                'ORACLE',
                                'FILE',
                                'API',
                                'S3',
                                'SFTP',
                                'OTHER'
                            )
                        ),
    host_name           text,
    environment         text NOT NULL
                        CHECK (environment IN ('DEV', 'TEST', 'REC', 'PROD')),
    criticality         text NOT NULL
                        CHECK (criticality IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    active              boolean NOT NULL DEFAULT true,
    created_at          timestamptz NOT NULL,
    updated_at          timestamptz NOT NULL
);

COMMENT ON TABLE ops.data_sources IS
'Enterprise data sources used by analytics applications.';


-- ============================================================
-- 3. Application dependencies
-- ============================================================

CREATE TABLE IF NOT EXISTS ops.application_dependencies (
    dependency_id       bigint PRIMARY KEY,
    application_id      integer NOT NULL
                        REFERENCES ops.applications(application_id),
    data_source_id      integer NOT NULL
                        REFERENCES ops.data_sources(data_source_id),
    dependency_type     text NOT NULL
                        CHECK (dependency_type IN ('PRIMARY', 'SECONDARY', 'OPTIONAL')),
    critical_path       boolean NOT NULL DEFAULT false,
    active              boolean NOT NULL DEFAULT true,
    created_at          timestamptz NOT NULL,
    UNIQUE (application_id, data_source_id)
);

COMMENT ON TABLE ops.application_dependencies IS
'Mapping between applications and the data sources they depend on.';


-- ============================================================
-- 4. Reload jobs
-- ============================================================

CREATE TABLE IF NOT EXISTS ops.reload_jobs (
    reload_id           bigint PRIMARY KEY,
    application_id      integer NOT NULL
                        REFERENCES ops.applications(application_id),
    started_at          timestamptz NOT NULL,
    ended_at            timestamptz,
    status              text NOT NULL
                        CHECK (
                            status IN (
                                'RUNNING',
                                'SUCCESS',
                                'FAILED',
                                'CANCELLED',
                                'SKIPPED'
                            )
                        ),
    duration_seconds    integer,
    rows_loaded         bigint NOT NULL DEFAULT 0,
    trigger_type        text NOT NULL
                        CHECK (
                            trigger_type IN (
                                'SCHEDULED',
                                'MANUAL',
                                'API',
                                'DEPENDENCY'
                            )
                        ),
    node_name           text NOT NULL,
    attempt_number      smallint NOT NULL DEFAULT 1
                        CHECK (attempt_number >= 1),
    sla_breached        boolean NOT NULL DEFAULT false,
    created_at          timestamptz NOT NULL
);

COMMENT ON TABLE ops.reload_jobs IS
'Reload executions for BI / analytics applications.';


-- ============================================================
-- 5. Reload logs — partitioned by month
-- ============================================================

CREATE TABLE IF NOT EXISTS ops.reload_logs (
    log_id              bigint NOT NULL,
    reload_id           bigint NOT NULL
                        REFERENCES ops.reload_jobs(reload_id),
    logged_at           timestamptz NOT NULL,
    level               text NOT NULL
                        CHECK (level IN ('DEBUG', 'INFO', 'WARN', 'ERROR', 'CRITICAL')),
    component           text NOT NULL,
    message             text NOT NULL,
    error_code          text,
    data_source_id      integer
                        REFERENCES ops.data_sources(data_source_id),
    correlation_id      uuid,
    PRIMARY KEY (logged_at, log_id)
) PARTITION BY RANGE (logged_at);

COMMENT ON TABLE ops.reload_logs IS
'High-volume technical reload logs. Partitioned monthly for scale.';


-- Monthly partitions: Jan 2024 through Sep 2026
DO $$
DECLARE
    partition_start date := DATE '2024-01-01';
    partition_end   date := DATE '2026-10-01';
    next_month      date;
    partition_name  text;
BEGIN
    WHILE partition_start < partition_end LOOP
        next_month := (partition_start + INTERVAL '1 month')::date;
        partition_name := format(
            'reload_logs_%s',
            to_char(partition_start, 'YYYY_MM')
        );

        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS ops.%I
             PARTITION OF ops.reload_logs
             FOR VALUES FROM (%L) TO (%L)',
            partition_name,
            partition_start,
            next_month
        );

        partition_start := next_month;
    END LOOP;
END $$;

CREATE TABLE IF NOT EXISTS ops.reload_logs_default
PARTITION OF ops.reload_logs DEFAULT;


-- ============================================================
-- 6. Incidents
-- ============================================================

CREATE TABLE IF NOT EXISTS ops.incidents (
    incident_id         bigint PRIMARY KEY,
    application_id      integer NOT NULL
                        REFERENCES ops.applications(application_id),
    opened_at           timestamptz NOT NULL,
    closed_at           timestamptz,
    severity            text NOT NULL
                        CHECK (severity IN ('SEV1', 'SEV2', 'SEV3', 'SEV4')),
    status              text NOT NULL
                        CHECK (
                            status IN (
                                'OPEN',
                                'INVESTIGATING',
                                'RESOLVED',
                                'CLOSED'
                            )
                        ),
    category            text NOT NULL,
    description         text NOT NULL,
    root_cause          text,
    detected_by         text NOT NULL,
    created_at          timestamptz NOT NULL,
    updated_at          timestamptz NOT NULL
);

COMMENT ON TABLE ops.incidents IS
'Operational incidents associated with analytics applications.';


-- ============================================================
-- 7. Incident events
-- ============================================================

CREATE TABLE IF NOT EXISTS ops.incident_events (
    event_id            bigint PRIMARY KEY,
    incident_id         bigint NOT NULL
                        REFERENCES ops.incidents(incident_id),
    occurred_at         timestamptz NOT NULL,
    event_type          text NOT NULL,
    source              text NOT NULL,
    message             text NOT NULL,
    created_at          timestamptz NOT NULL
);

COMMENT ON TABLE ops.incident_events IS
'Chronological events attached to incidents.';


-- ============================================================
-- 8. Jira tickets
-- ============================================================

CREATE TABLE IF NOT EXISTS ops.jira_tickets (
    ticket_id           bigint PRIMARY KEY,
    jira_key            text NOT NULL UNIQUE,
    incident_id         bigint
                        REFERENCES ops.incidents(incident_id),
    created_at          timestamptz NOT NULL,
    updated_at          timestamptz NOT NULL,
    priority            text NOT NULL
                        CHECK (priority IN ('P1', 'P2', 'P3', 'P4')),
    status              text NOT NULL
                        CHECK (
                            status IN (
                                'OPEN',
                                'IN_PROGRESS',
                                'BLOCKED',
                                'RESOLVED',
                                'CLOSED'
                            )
                        ),
    assignee            text,
    summary             text NOT NULL,
    resolution          text
);

COMMENT ON TABLE ops.jira_tickets IS
'Synthetic Jira-like tickets linked to operational incidents.';


-- ============================================================
-- Indexes
-- ============================================================

-- Applications / dependencies
CREATE INDEX IF NOT EXISTS idx_applications_domain
    ON ops.applications (domain);

CREATE INDEX IF NOT EXISTS idx_dependencies_application
    ON ops.application_dependencies (application_id);

CREATE INDEX IF NOT EXISTS idx_dependencies_source
    ON ops.application_dependencies (data_source_id);

-- Reload jobs
CREATE INDEX IF NOT EXISTS idx_reload_jobs_app_started
    ON ops.reload_jobs (application_id, started_at DESC);

CREATE INDEX IF NOT EXISTS idx_reload_jobs_status_started
    ON ops.reload_jobs (status, started_at DESC);

CREATE INDEX IF NOT EXISTS idx_reload_jobs_sla_breached
    ON ops.reload_jobs (application_id, started_at DESC)
    WHERE sla_breached = true;

CREATE INDEX IF NOT EXISTS idx_reload_jobs_started_brin
    ON ops.reload_jobs USING BRIN (started_at);

-- Reload logs: parent partitioned indexes are propagated to partitions
CREATE INDEX IF NOT EXISTS idx_reload_logs_reload_time
    ON ops.reload_logs (reload_id, logged_at);

CREATE INDEX IF NOT EXISTS idx_reload_logs_level_time
    ON ops.reload_logs (level, logged_at DESC);

CREATE INDEX IF NOT EXISTS idx_reload_logs_error_code
    ON ops.reload_logs (error_code, logged_at DESC)
    WHERE error_code IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_reload_logs_data_source
    ON ops.reload_logs (data_source_id, logged_at DESC)
    WHERE data_source_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_reload_logs_logged_brin
    ON ops.reload_logs USING BRIN (logged_at);

-- Incidents
CREATE INDEX IF NOT EXISTS idx_incidents_app_opened
    ON ops.incidents (application_id, opened_at DESC);

CREATE INDEX IF NOT EXISTS idx_incidents_status
    ON ops.incidents (status, opened_at DESC);

CREATE INDEX IF NOT EXISTS idx_incidents_severity
    ON ops.incidents (severity, opened_at DESC);

-- Incident events
CREATE INDEX IF NOT EXISTS idx_incident_events_incident_time
    ON ops.incident_events (incident_id, occurred_at);

-- Jira
CREATE INDEX IF NOT EXISTS idx_jira_incident
    ON ops.jira_tickets (incident_id);

CREATE INDEX IF NOT EXISTS idx_jira_status_priority
    ON ops.jira_tickets (status, priority);


COMMIT;
