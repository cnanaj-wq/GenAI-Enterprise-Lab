-- GenAI Enterprise Lab
-- Module 1 — corrective migration
-- Adds an explicit link between incidents and reload jobs.

BEGIN;

ALTER TABLE ops.incidents
    ADD COLUMN IF NOT EXISTS reload_id bigint
    REFERENCES ops.reload_jobs(reload_id);

CREATE INDEX IF NOT EXISTS idx_incidents_reload
    ON ops.incidents (reload_id)
    WHERE reload_id IS NOT NULL;

COMMENT ON COLUMN ops.incidents.reload_id IS
'Reload job directly associated with the incident when the incident was triggered by a reload failure.';

COMMIT;
