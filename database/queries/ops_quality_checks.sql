-- GenAI Enterprise Lab
-- Module 1 — STEP 1.3D
-- Data quality and anomaly validation queries
--
-- Purpose:
--   Validate that the synthetic DEV/BENCHMARK dataset is coherent before
--   exposing it to LangGraph agents and MCP tools.

-- ============================================================
-- 1. Global row counts
-- ============================================================

SELECT
    (SELECT count(*) FROM ops.applications) AS applications,
    (SELECT count(*) FROM ops.data_sources) AS data_sources,
    (SELECT count(*) FROM ops.application_dependencies) AS dependencies,
    (SELECT count(*) FROM ops.reload_jobs) AS reload_jobs,
    (SELECT count(*) FROM ops.reload_logs) AS reload_logs,
    (SELECT count(*) FROM ops.incidents) AS incidents,
    (SELECT count(*) FROM ops.incident_events) AS incident_events,
    (SELECT count(*) FROM ops.jira_tickets) AS jira_tickets;


-- ============================================================
-- 2. Reload status distribution
-- ============================================================

SELECT
    status,
    count(*) AS reload_count,
    round(100.0 * count(*) / sum(count(*)) OVER (), 2) AS pct
FROM ops.reload_jobs
GROUP BY status
ORDER BY reload_count DESC;


-- ============================================================
-- 3. SLA breach rate
-- ============================================================

SELECT
    count(*) FILTER (WHERE sla_breached) AS sla_breaches,
    count(*) AS total_reloads,
    round(
        100.0 * count(*) FILTER (WHERE sla_breached) / count(*),
        2
    ) AS sla_breach_pct
FROM ops.reload_jobs;


-- ============================================================
-- 4. Failed reloads without an incident
--    This is intentionally possible in the synthetic dataset.
-- ============================================================

SELECT
    count(*) AS failed_without_incident
FROM ops.reload_jobs r
LEFT JOIN ops.incidents i
    ON i.application_id = r.application_id
   AND i.opened_at BETWEEN r.started_at - INTERVAL '15 minutes'
                       AND r.ended_at + INTERVAL '30 minutes'
WHERE r.status = 'FAILED'
  AND i.incident_id IS NULL;


-- ============================================================
-- 5. Successful reloads that still breached SLA
--    Important business case: technical success != SLA success.
-- ============================================================

SELECT
    count(*) AS success_but_sla_breached
FROM ops.reload_jobs
WHERE status = 'SUCCESS'
  AND sla_breached = true;


-- ============================================================
-- 6. Root-cause / incident category distribution
-- ============================================================

SELECT
    category,
    count(*) AS incident_count,
    round(100.0 * count(*) / sum(count(*)) OVER (), 2) AS pct
FROM ops.incidents
GROUP BY category
ORDER BY incident_count DESC;


-- ============================================================
-- 7. Log level distribution
-- ============================================================

SELECT
    level,
    count(*) AS log_count,
    round(100.0 * count(*) / sum(count(*)) OVER (), 2) AS pct
FROM ops.reload_logs
GROUP BY level
ORDER BY log_count DESC;


-- ============================================================
-- 8. Error-code distribution
-- ============================================================

SELECT
    error_code,
    count(*) AS occurrences
FROM ops.reload_logs
WHERE error_code IS NOT NULL
GROUP BY error_code
ORDER BY occurrences DESC
LIMIT 20;


-- ============================================================
-- 9. Referential-integrity validation
--    All results should be 0.
-- ============================================================

SELECT
    'reload_jobs_without_application' AS check_name,
    count(*) AS invalid_rows
FROM ops.reload_jobs r
LEFT JOIN ops.applications a
    ON a.application_id = r.application_id
WHERE a.application_id IS NULL

UNION ALL

SELECT
    'reload_logs_without_reload_job',
    count(*)
FROM ops.reload_logs l
LEFT JOIN ops.reload_jobs r
    ON r.reload_id = l.reload_id
WHERE r.reload_id IS NULL

UNION ALL

SELECT
    'incidents_without_application',
    count(*)
FROM ops.incidents i
LEFT JOIN ops.applications a
    ON a.application_id = i.application_id
WHERE a.application_id IS NULL

UNION ALL

SELECT
    'incident_events_without_incident',
    count(*)
FROM ops.incident_events e
LEFT JOIN ops.incidents i
    ON i.incident_id = e.incident_id
WHERE i.incident_id IS NULL

UNION ALL

SELECT
    'jira_without_incident',
    count(*)
FROM ops.jira_tickets j
LEFT JOIN ops.incidents i
    ON i.incident_id = j.incident_id
WHERE j.incident_id IS NOT NULL
  AND i.incident_id IS NULL;


-- ============================================================
-- 10. Reload-log coverage
--     Every reload should have logs in the current generator.
-- ============================================================

SELECT
    count(*) AS reloads_without_logs
FROM ops.reload_jobs r
LEFT JOIN ops.reload_logs l
    ON l.reload_id = r.reload_id
WHERE l.reload_id IS NULL;


-- ============================================================
-- 11. Average / min / max logs per reload
-- ============================================================

WITH per_reload AS (
    SELECT
        reload_id,
        count(*) AS logs_per_reload
    FROM ops.reload_logs
    GROUP BY reload_id
)
SELECT
    min(logs_per_reload) AS min_logs,
    round(avg(logs_per_reload), 2) AS avg_logs,
    max(logs_per_reload) AS max_logs
FROM per_reload;


-- ============================================================
-- 12. Applications with the most failed reloads
-- ============================================================

SELECT
    a.application_name,
    count(*) AS failed_reloads
FROM ops.reload_jobs r
JOIN ops.applications a
    ON a.application_id = r.application_id
WHERE r.status = 'FAILED'
GROUP BY a.application_name
ORDER BY failed_reloads DESC
LIMIT 15;


-- ============================================================
-- 13. Data sources linked to the most failed reloads
--     Useful for identifying shared upstream failures.
-- ============================================================

SELECT
    ds.data_source_name,
    count(DISTINCT r.reload_id) AS failed_reloads,
    count(DISTINCT r.application_id) AS impacted_applications
FROM ops.reload_jobs r
JOIN ops.application_dependencies d
    ON d.application_id = r.application_id
JOIN ops.data_sources ds
    ON ds.data_source_id = d.data_source_id
WHERE r.status = 'FAILED'
GROUP BY ds.data_source_name
ORDER BY failed_reloads DESC
LIMIT 15;


-- ============================================================
-- 14. Example investigation candidates
--     Pick recent failed reloads with evidence in the logs.
-- ============================================================

SELECT
    r.reload_id,
    a.application_name,
    r.started_at,
    r.ended_at,
    r.status,
    r.sla_breached,
    count(l.log_id) AS log_count,
    count(*) FILTER (WHERE l.level IN ('ERROR', 'CRITICAL')) AS error_logs,
    count(*) FILTER (WHERE l.level = 'WARN') AS warning_logs
FROM ops.reload_jobs r
JOIN ops.applications a
    ON a.application_id = r.application_id
JOIN ops.reload_logs l
    ON l.reload_id = r.reload_id
WHERE r.status = 'FAILED'
GROUP BY
    r.reload_id,
    a.application_name,
    r.started_at,
    r.ended_at,
    r.status,
    r.sla_breached
ORDER BY r.started_at DESC
LIMIT 10;


-- ============================================================
-- 15. Example causal timeline for one failed reload
--
-- Replace :reload_id manually with an ID from query #14.
-- Example:
--     WHERE l.reload_id = 1234
-- ============================================================

-- SELECT
--     l.logged_at,
--     l.level,
--     l.component,
--     l.message,
--     l.error_code,
--     ds.data_source_name
-- FROM ops.reload_logs l
-- LEFT JOIN ops.data_sources ds
--     ON ds.data_source_id = l.data_source_id
-- WHERE l.reload_id = :reload_id
-- ORDER BY l.logged_at;


-- ============================================================
-- 16. PostgreSQL relation sizes
-- ============================================================

SELECT
    n.nspname AS schema_name,
    c.relname AS relation_name,
    pg_size_pretty(pg_total_relation_size(c.oid)) AS total_size
FROM pg_class c
JOIN pg_namespace n
    ON n.oid = c.relnamespace
WHERE n.nspname = 'ops'
  AND c.relkind IN ('r', 'p')
ORDER BY pg_total_relation_size(c.oid) DESC
LIMIT 20;


-- ============================================================
-- 17. Total ops schema size
-- ============================================================

SELECT
    pg_size_pretty(
        sum(pg_total_relation_size(c.oid))
    ) AS ops_schema_size
FROM pg_class c
JOIN pg_namespace n
    ON n.oid = c.relnamespace
WHERE n.nspname = 'ops'
  AND c.relkind IN ('r', 'p');
