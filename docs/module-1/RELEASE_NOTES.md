# Module 1 Release Notes

## Release candidate

Branch: `module-1-agentic-ai`

Final remote CI state:

```text
Module 1 CI       SUCCESS
python-quality    SUCCESS
frontend-quality  SUCCESS
```

## Main delivered capabilities

- AI Ops Investigator
- LangGraph stateful orchestration
- MCP server + client
- 6 read-only enterprise tools
- OpenAI-backed diagnosis
- deterministic LLM fallback
- MCP timeout/retry/backoff/circuit breaker
- trace/span/event observability
- SSE live event stream
- Next.js agent graph
- history and replay
- trace comparison
- GenAI FinOps
- project health / CI-CD cockpit
- deterministic OPTIMIZE control tower
- local quality gate
- GitHub Actions pipeline

## Final local quality gate

```text
RUFF             PASS
PYTEST           PASS
ESLINT           PASS
NEXTJS_BUILD     PASS
Project Health   RECORDED
Overall          PASS
```

## Remote CI incident that improved the release

The first remote pipeline failed because the local database had pgvector activated while a fresh GitHub Actions database did not.

The image contained pgvector, but PostgreSQL had no `vector` extension registered.

The fix was to make the requirement explicit:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

Subsequent remote CI runs passed.

This incident is retained in the engineering history because it demonstrates environment reproducibility and the purpose of CI.
