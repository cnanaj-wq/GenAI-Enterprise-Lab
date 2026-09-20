# STEP 1.4C — FastAPI + SSE Live Event Streaming

This step streams the already persisted Trace / Span / Event telemetry from
FastAPI to a browser/client in real time.

## Architecture

```text
POST /api/v1/investigations
        |
        +--> background deterministic investigation
        |       |
        |       +--> TelemetryRecorder
        |                |
        |                +--> PostgreSQL observability.*
        |                |
        |                +--> LiveEventBroker
        |
GET /api/v1/investigations/{run_id}/stream
        |
        +--> SSE
        |
        +--> Next.js (STEP 1.4D)
```

## Important

There is still **no LLM and no LangGraph** in this step.
We first validate the real-time transport independently.

The local broker is in memory. This is correct for the training/dev phase.
A production multi-worker architecture will later use a shared transport such
as Redis, GCP Pub/Sub or Kafka.

## Install

Extract this archive into:

`C:\GenAI-Enterprise-Lab`

It adds/replaces:

- `apps/api/app/main.py`
- `apps/api/app/observability/live_stream.py`
- `apps/api/app/routes/__init__.py`
- `apps/api/app/routes/investigations.py`
- `apps/api/app/services/__init__.py`
- `apps/api/app/services/investigation_service.py`
- `scripts/test_sse_stream.py`

## Terminal 1 — Start FastAPI

```powershell
cd C:\GenAI-Enterprise-Lab
.\.venv\Scripts\Activate.ps1
python -m uvicorn apps.api.app.main:app --reload --port 8000
```

## Terminal 2 — Run the SSE smoke test

```powershell
cd C:\GenAI-Enterprise-Lab
.\.venv\Scripts\Activate.ps1
python scripts\test_sse_stream.py
```

The final event contains the 100% execution breakdown:

```text
TOTAL = 100%
TOOLS = xx.x%
UNATTRIBUTED = yy.y%
```

`UNATTRIBUTED` is intentionally not called pure telemetry overhead yet.
At this stage it includes orchestration, telemetry persistence and other
runtime overhead. Later OpenTelemetry instrumentation will allow finer
decomposition.
