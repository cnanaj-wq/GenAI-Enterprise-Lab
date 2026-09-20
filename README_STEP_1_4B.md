# STEP 1.4B — Trace / Span / Event Store

This step adds persistent observability before LangGraph.

## What gets stored

- `observability.traces`: one complete prompt execution
- `observability.spans`: one timed execution step
- `observability.events`: ordered runtime events

## Install

Copy the archive contents into:

`C:\GenAI-Enterprise-Lab`

Apply the migration:

```powershell
Get-Content .\database\migrations\003_observability_schema.sql -Raw |
  docker exec -i genai-postgres psql -U genai -d genai_lab
```

Run the smoke test:

```powershell
python scripts\test_observability.py
```

Expected shape:

```text
trace_started
span_started / span_finished
...
trace_finished

Persisted trace
Persisted spans
Events persisted : ...
STEP 1.4B telemetry smoke test complete.
```

This is the storage foundation for the future Next.js LIVE / HISTORY / REPLAY / COMPARE / OPTIMIZE cockpit.
