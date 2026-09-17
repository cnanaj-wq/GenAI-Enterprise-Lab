# STEP 1.7A — MCP v2 Server

We now expose the six validated AI Ops tools through the official Model
Context Protocol Python SDK v2.

## Architecture

Before:

```text
LangGraph -> Python tool -> PostgreSQL
```

After MCP exposure:

```text
Any MCP host/client
        |
        | Model Context Protocol
        v
MCP Server :8001/mcp
        |
Existing Python tools
        |
PostgreSQL
```

The MCP layer standardizes access; it does not duplicate the business logic.

## 1. Install MCP v2

```powershell
cd C:\GenAI-Enterprise-Lab
.\.venv\Scripts\Activate.ps1

python -m pip install "mcp[cli]>=2,<3"
```

Persist it:

```powershell
if (-not (Select-String -Path .\requirements.txt -Pattern '^mcp' -Quiet)) {
    Add-Content .\requirements.txt "`n# Model Context Protocol SDK v2`nmcp[cli]>=2,<3"
}
python -m pip freeze > requirements.lock.txt
```

## 2. Extract this archive

Extract into:

`C:\GenAI-Enterprise-Lab`

It adds:

- `apps/mcp/__init__.py`
- `apps/mcp/server.py`
- `scripts/test_mcp_client.py`

## 3. Start the MCP server

Use a dedicated terminal:

```powershell
cd C:\GenAI-Enterprise-Lab
.\.venv\Scripts\Activate.ps1
python -m apps.mcp.server
```

Endpoint:

```text
http://127.0.0.1:8001/mcp
```

Keep FastAPI on port 8000. MCP uses 8001.

## 4. Test with the official MCP client

Another terminal:

```powershell
cd C:\GenAI-Enterprise-Lab
.\.venv\Scripts\Activate.ps1
python scripts\test_mcp_client.py
```

The test:
- negotiates the MCP protocol
- lists the six tools and their JSON schemas
- calls `get_application`
- calls `get_reload_history`
- calls `get_reload_logs`
- reads `ops://manifest`

## 5. Optional MCP Inspector

```powershell
npx -y @modelcontextprotocol/inspector
```

Connect to:

```text
http://127.0.0.1:8001/mcp
```

## Security rule

This MCP server is read-only.

It exposes no arbitrary SQL, filesystem, shell, INSERT, UPDATE, DELETE or DROP.

## Next — STEP 1.7B

LangGraph will stop calling the Python functions directly and will consume
the exact same enterprise tools through MCP:

```text
LangGraph
   |
MCP Client
   |
MCP Server
   |
Python Tools
   |
PostgreSQL
```

That is the point where MCP becomes the actual standardized "prise" between
the orchestrator and the enterprise tool layer.
