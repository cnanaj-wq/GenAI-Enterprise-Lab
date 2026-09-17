# STEP 1.5 — LangGraph Orchestration

LangGraph becomes the orchestration engine of the AI Ops Investigator.

The LLM is **not connected yet**. This is intentional.

## Mental model

```text
LLM        = brain          (STEP 1.6)
LangGraph  = nervous system / orchestrator   <-- NOW
Tools      = hands
PostgreSQL = business memory
MCP        = standard connector              (later)
```

## Workflow

```text
START
  |
select_candidate
  |
load_application
  |
inspect_reload_history
  |
inspect_reload_logs
  |
lookup_incident
  |
  +-- incident exists --> lookup_jira --------+
  |                                           |
  +-- no incident ----------------------------+
                                              |
                                    inspect_dependencies
                                              |
                                        build_summary
                                              |
                                             END
```

Every LangGraph node is persisted as a `NODE` span.
Every business tool call is a child `TOOL` span.

## 1. Install LangGraph

From the project virtual environment:

```powershell
cd C:\GenAI-Enterprise-Lab
.\.venv\Scripts\Activate.ps1
python -m pip install "langgraph==1.2.11"
```

Persist the dependency in `requirements.txt`:

```powershell
if (-not (Select-String -Path .\requirements.txt -Pattern '^langgraph==' -Quiet)) {
    Add-Content .\requirements.txt "`n# Agent workflow orchestration`nlanggraph==1.2.11"
}
```

Refresh the lock file:

```powershell
python -m pip freeze > requirements.lock.txt
```

## 2. Extract the archive

Extract into:

`C:\GenAI-Enterprise-Lab`

It adds:

- `apps/api/app/agents/__init__.py`
- `apps/api/app/agents/ai_ops_graph.py`
- `scripts/test_langgraph_structure.py`

It replaces:

- `apps/api/app/services/investigation_service.py`

FastAPI routes, SSE and the Next.js cockpit stay unchanged.

## 3. Validate the graph structure

```powershell
python scripts\test_langgraph_structure.py
```

You should see the nodes, edges and a Mermaid representation.

## 4. Restart FastAPI

```powershell
python -m uvicorn apps.api.app.main:app --reload --port 8000
```

## 5. Re-run from the cockpit

Keep Next.js running or restart it:

```powershell
cd C:\GenAI-Enterprise-Lab\apps\web
npm run dev
```

Open:

`http://localhost:3000`

Click **Lancer**.

The existing cockpit now observes a real LangGraph workflow without changing
the SSE contract.

## What changes in the trace

Before STEP 1.5:

```text
TOOL get_application
TOOL get_reload_history
...
```

After STEP 1.5:

```text
NODE select_candidate
  DATABASE discover_failed_reload

NODE load_application
  TOOL get_application

NODE inspect_reload_history
  TOOL get_reload_history

...
```

This is the first point where the cockpit is literally showing the
orchestrator's nervous system.
