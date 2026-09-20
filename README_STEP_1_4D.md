# STEP 1.4D — Next.js Live Agent Inspector

This step visualizes the FastAPI SSE stream in the browser.

## 1. Extract

Extract into:

`C:\GenAI-Enterprise-Lab`

This replaces:

- `apps/web/src/app/page.tsx`

## 2. Install React Flow

From the web app:

```powershell
cd C:\GenAI-Enterprise-Lab\apps\web
npm install @xyflow/react
```

## 3. Start FastAPI

Terminal 1:

```powershell
cd C:\GenAI-Enterprise-Lab
.\.venv\Scripts\Activate.ps1
python -m uvicorn apps.api.app.main:app --reload --port 8000
```

## 4. Start Next.js

Terminal 2:

```powershell
cd C:\GenAI-Enterprise-Lab\apps\web
npm run dev
```

Then open:

`http://localhost:3000`

## What you should see

- prompt input
- application input
- RUNNING / SUCCESS / ERROR status
- start/end timestamps
- run_id / trace_id
- live React Flow graph
- live SSE event stream
- total trace duration
- pure tool time
- unattributed time
- percentages on 100%
- span total
- error count
- investigation summary

## Important

The current graph is still deterministic and has no LangGraph/LLM.
That is intentional.

Next steps:

- STEP 1.5: LangGraph orchestration
- STEP 1.6: LLM integration
- later: HISTORY / REPLAY / COMPARE / OPTIMIZE

The event contract and UI stay reusable when LangGraph replaces the deterministic runner.
