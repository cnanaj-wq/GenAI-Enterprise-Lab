# STEP 1.4A v3 — SQL Tools

Fixes:
- PostgreSQL `AmbiguousParameter` removed by building optional filters explicitly.
- Same fix applied proactively to `get_reload_logs(level=...)`.
- Smoke test now adds the repository root to `sys.path`, so manual `PYTHONPATH` is no longer required.

Run:

```powershell
cd C:\GenAI-Enterprise-Lab
python scripts\test_ops_tools.py
```
