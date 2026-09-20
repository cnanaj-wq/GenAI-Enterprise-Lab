# STEP 1.5B — Visual hierarchy in the Live Agent Graph

Small visual upgrade before STEP 1.6.

## Changes

- NODE LangGraph = purple
- TOOL = blue
- DATABASE = orange
- LLM = green
- EVALUATION = yellow
- ERROR = red
- child spans are rendered to the right of their parent NODE
- EVENT STREAM gets zebra striping for readability
- legend added above the graph

## Backend adjustment

`TelemetryRecorder.start_span()` now includes `parent_span_id` in the
`span_started` SSE event. The database schema does not change.

## Install

Extract into:

`C:\GenAI-Enterprise-Lab`

It replaces:

- `apps/api/app/observability/telemetry.py`
- `apps/web/src/app/page.tsx`

No new npm or pip dependency is required.

FastAPI with `--reload` should reload automatically. If needed, restart it.

Then refresh `http://localhost:3000` and click **Lancer** again.
