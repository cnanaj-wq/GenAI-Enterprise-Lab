# STEP 1.6 — Real LLM integration (OpenAI Responses API)

This step adds the **brain** to the AI Ops Investigator.

## Architecture

```text
User prompt
    |
LangGraph
    |
    +--> NODE / TOOL / DATABASE
    |
    +--> NODE generate_llm_diagnosis
              |
              +--> LLM span (OpenAI)
                       |
                       +--> tokens
                       +--> latency
                       +--> estimated cost
                       +--> grounded diagnosis
```

The existing SSE + Next.js cockpit displays the LLM span in green.

## Default model

`gpt-5.6-luna`

It is configurable through `.env`.

## 1. Install the OpenAI SDK

```powershell
cd C:\GenAI-Enterprise-Lab
.\.venv\Scripts\Activate.ps1
python -m pip install openai
```

Persist it in requirements.txt:

```powershell
if (-not (Select-String -Path .\requirements.txt -Pattern '^openai' -Quiet)) {
    Add-Content .\requirements.txt "`n# OpenAI Responses API SDK`nopenai"
}
python -m pip freeze > requirements.lock.txt
```

## 2. Add the API configuration to `.env`

Do NOT commit the API key.

```text
OPENAI_API_KEY=YOUR_KEY_HERE
OPENAI_MODEL=gpt-5.6-luna
OPENAI_MAX_OUTPUT_TOKENS=700
```

The project's `.gitignore` already ignores `.env`.

## 3. Extract this archive

Extract into:

`C:\GenAI-Enterprise-Lab`

It adds/replaces:

- `apps/api/app/config.py`
- `apps/api/app/llm/__init__.py`
- `apps/api/app/llm/openai_provider.py`
- `apps/api/app/agents/ai_ops_graph.py`
- `apps/api/app/services/investigation_service.py`
- `apps/web/src/app/page.tsx`
- `scripts/test_llm_connection.py`

## 4. Test the LLM directly

```powershell
python scripts\test_llm_connection.py
```

You should see:
- model
- diagnosis
- input/output/total tokens
- estimated cost

## 5. Restart FastAPI and Next.js

FastAPI:

```powershell
python -m uvicorn apps.api.app.main:app --reload --port 8000
```

Next.js:

```powershell
cd C:\GenAI-Enterprise-Lab\apps\web
npm run dev
```

Then open:

`http://localhost:3000`

Click **Lancer**.

## New cockpit metrics

- LLM duration and % of trace
- input/output/total tokens
- estimated USD cost
- green LLM span
- grounded diagnosis panel

## Important

ChatGPT subscriptions and OpenAI API billing are separate products. The API
key must be created for the API platform and kept only in local secrets /
enterprise secret management.
