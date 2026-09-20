BEGIN;

ALTER TABLE observability.spans
    DROP CONSTRAINT IF EXISTS spans_span_type_check;

ALTER TABLE observability.spans
    ADD CONSTRAINT spans_span_type_check
    CHECK (
        span_type IN (
            'NODE',
            'TOOL',
            'MCP',
            'LLM',
            'DATABASE',
            'EVALUATION',
            'OTHER'
        )
    );

COMMIT;
