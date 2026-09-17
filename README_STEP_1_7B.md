# STEP 1.7B — LangGraph consumes enterprise tools through MCP

This is the real MCP integration step.

## Before

```text
LangGraph -> Python functions -> PostgreSQL
```

## After

```text
LangGraph
   |
   v
MCP Client
   |
   v
MCP Server :8001/mcp
   |
   v
Python tools
   |
   v
PostgreSQL
```

The LLM remains OpenAI and the cockpit remains Next.js + SSE.

## New observability category

```text
NODE        purple
MCP         cyan
DATABASE    orange
LLM         green
EVALUATION  yellow
ERROR       red
```

A LangGraph node now looks like:

```text
NODE inspect_reload_logs
    |
    +-- MCP mcp:get_reload_logs
```

The MCP span measures the **end-to-end round-trip**:

```text
client
+ HTTP transport
+ MCP server
+ remote Python tool
+ PostgreSQL query
+ MCP response
```

It is therefore not pure "MCP overhead".

## 1. Extract

Extract this archive into:

`C:\GenAI-Enterprise-Lab`

## 2. Apply the migration

```powershell
cd C:\GenAI-Enterprise-Lab

Get-Content .\database\migrations\004_observability_mcp_span.sql -Raw |
  docker exec -i genai-postgres psql -U genai -d genai_lab
```

Expected:

```text
BEGIN
ALTER TABLE
ALTER TABLE
COMMIT
```

## 3. Optional `.env`

The default is already:

```text
MCP_URL=http://127.0.0.1:8001/mcp
```

You only need to add it if you want the endpoint explicit in `.env`.

## 4. Run the required processes

MCP server:

```powershell
cd C:\GenAI-Enterprise-Lab
.\.venv\Scripts\Activate.ps1
python -m apps.mcp.server
```

FastAPI:

```powershell
cd C:\GenAI-Enterprise-Lab
.\.venv\Scripts\Activate.ps1
python -m uvicorn apps.api.app.main:app --reload --port 8000
```

Next.js:

```powershell
cd C:\GenAI-Enterprise-Lab\apps\web
npm run dev
```

## 5. Smoke test

```powershell
cd C:\GenAI-Enterprise-Lab
.\.venv\Scripts\Activate.ps1
python scripts\test_langgraph_mcp.py
```

## 6. Cockpit

Open:

`http://localhost:3000`

You should see:

```text
MCP ● CONNECTED

NODE load_application
    MCP mcp:get_application

NODE inspect_reload_history
    MCP mcp:get_reload_history

NODE inspect_reload_logs
    MCP mcp:get_reload_logs
...
```

The execution breakdown becomes:

```text
TOTAL          100 %
MCP round-trip  xx %
LLM             xx %
Unattributed    xx %
```

## Important architecture note

`select_candidate` still performs one internal database lookup directly.
That lookup is orchestration infrastructure and is shown as a DATABASE span.

All six enterprise business tools are now consumed by LangGraph through MCP.
