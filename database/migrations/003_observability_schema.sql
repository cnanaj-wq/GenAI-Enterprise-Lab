BEGIN;

CREATE SCHEMA IF NOT EXISTS observability;

CREATE TABLE IF NOT EXISTS observability.traces (
    trace_id            uuid PRIMARY KEY,
    conversation_id     uuid,
    prompt              text NOT NULL,
    status              text NOT NULL
                        CHECK (status IN ('RUNNING', 'SUCCESS', 'ERROR', 'CANCELLED')),
    started_at          timestamptz NOT NULL,
    finished_at         timestamptz,
    duration_ms         bigint,
    provider            text,
    model               text,
    prompt_version      text,
    input_tokens        integer,
    output_tokens       integer,
    estimated_cost_usd  numeric(14, 6),
    error_type          text,
    error_message       text,
    created_at          timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS observability.spans (
    span_id          uuid PRIMARY KEY,
    trace_id         uuid NOT NULL
                     REFERENCES observability.traces(trace_id)
                     ON DELETE CASCADE,
    parent_span_id   uuid
                     REFERENCES observability.spans(span_id)
                     ON DELETE SET NULL,
    sequence_no      integer NOT NULL,
    span_type        text NOT NULL
                     CHECK (span_type IN (
                         'NODE',
                         'TOOL',
                         'LLM',
                         'DATABASE',
                         'EVALUATION',
                         'OTHER'
                     )),
    name             text NOT NULL,
    status           text NOT NULL
                     CHECK (status IN ('RUNNING', 'SUCCESS', 'ERROR', 'CANCELLED')),
    started_at       timestamptz NOT NULL,
    finished_at      timestamptz,
    duration_ms      bigint,
    input_json       jsonb,
    output_json      jsonb,
    error_type       text,
    error_message    text,
    metadata_json    jsonb,
    created_at       timestamptz NOT NULL DEFAULT now(),
    UNIQUE (trace_id, sequence_no)
);

CREATE TABLE IF NOT EXISTS observability.events (
    event_id         bigserial PRIMARY KEY,
    trace_id         uuid NOT NULL
                     REFERENCES observability.traces(trace_id)
                     ON DELETE CASCADE,
    span_id          uuid
                     REFERENCES observability.spans(span_id)
                     ON DELETE CASCADE,
    event_type       text NOT NULL,
    occurred_at      timestamptz NOT NULL,
    sequence_no      bigint NOT NULL,
    event_data       jsonb,
    created_at       timestamptz NOT NULL DEFAULT now(),
    UNIQUE (trace_id, sequence_no)
);

CREATE INDEX IF NOT EXISTS idx_observability_traces_started
    ON observability.traces (started_at DESC);

CREATE INDEX IF NOT EXISTS idx_observability_traces_status_started
    ON observability.traces (status, started_at DESC);

CREATE INDEX IF NOT EXISTS idx_observability_spans_trace_sequence
    ON observability.spans (trace_id, sequence_no);

CREATE INDEX IF NOT EXISTS idx_observability_spans_name_started
    ON observability.spans (name, started_at DESC);

CREATE INDEX IF NOT EXISTS idx_observability_events_trace_sequence
    ON observability.events (trace_id, sequence_no);

CREATE INDEX IF NOT EXISTS idx_observability_events_occurred
    ON observability.events (occurred_at DESC);

COMMENT ON SCHEMA observability IS
    'Runtime traces, spans and events emitted by GenAI agents and tools.';

COMMENT ON TABLE observability.traces IS
    'One row per complete prompt/agent execution.';

COMMENT ON TABLE observability.spans IS
    'One row per measurable execution step inside a trace.';

COMMENT ON TABLE observability.events IS
    'Fine-grained ordered runtime events used for history and live streaming.';

COMMIT;
