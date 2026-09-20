# STEP 1.7A.1 — MCP Gateway in FastAPI

Your screenshot currently shows only:

- investigations
- default

This patch adds a new **mcp** section to Swagger on port 8000.

## Architecture

```text
Browser / Swagger / Next.js
            |
            v
FastAPI :8000
            |
            | MCP Client
            v
MCP Server :8001/mcp
            |
            v
AI Ops Tools
            |
            v
PostgreSQL
```

## Routes added

```text
GET /api/v1/mcp/status
GET /api/v1/mcp/tools
GET /api/v1/mcp/manifest
```

## Install

Extract into:

`C:\GenAI-Enterprise-Lab`

It adds/replaces:

- `apps/api/app/routes/mcp_gateway.py`
- `apps/api/app/main.py`

No new dependency is needed beyond the MCP SDK already installed for STEP 1.7A.

## Required processes

Terminal 1 — PostgreSQL/Docker must be up.

Terminal 2 — MCP server:

```powershell
cd C:\GenAI-Enterprise-Lab
.\.venv\Scripts\Activate.ps1
python -m apps.mcp.server
```

Terminal 3 — FastAPI:

```powershell
cd C:\GenAI-Enterprise-Lab
.\.venv\Scripts\Activate.ps1
python -m uvicorn apps.api.app.main:app --reload --port 8000
```

## Verify

Open:

`http://127.0.0.1:8000/docs`

You should now see:

```text
investigations
mcp
default
```

Direct endpoints:

```text
http://127.0.0.1:8000/api/v1/mcp/status
http://127.0.0.1:8000/api/v1/mcp/tools
http://127.0.0.1:8000/api/v1/mcp/manifest
```

If the MCP server on port 8001 is not running, these routes return HTTP 503.
