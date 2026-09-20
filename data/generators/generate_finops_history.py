from __future__ import annotations

import math
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from apps.api.app.database import engine

SEED, DAYS = 42, 120

BUS = [
    ("IT & Data", 2200),
    ("Finance", 1800),
    ("Sales", 1500),
    ("Operations", 1600),
    ("Customer Service", 1700),
    ("Product & Engineering", 2400),
]
TEAMS = [
    ("Data Platform", "IT & Data", 1200),
    ("AI Enablement", "IT & Data", 1100),
    ("FP&A", "Finance", 950),
    ("Risk Analytics", "Finance", 950),
    ("Sales Operations", "Sales", 800),
    ("Revenue Intelligence", "Sales", 800),
    ("Process Excellence", "Operations", 850),
    ("Supply Analytics", "Operations", 850),
    ("Customer Care", "Customer Service", 900),
    ("Knowledge Operations", "Customer Service", 900),
    ("Product Analytics", "Product & Engineering", 1200),
    ("Developer Experience", "Product & Engineering", 1300),
]
USES = [
    ("AI Ops Investigator", "Incident investigation through tools/logs", 1300),
    ("Enterprise Knowledge Copilot", "Enterprise RAG assistant", 1800),
    ("Customer Support Assistant", "High-volume support assistant", 1600),
    ("Data Analyst Copilot", "SQL and analytical reasoning", 2200),
    ("Developer Assistant", "Code generation and review", 2300),
]
MODELS = [
    ("gpt-5.6-luna", 0.20, 1.20, "ECONOMY"),
    ("gpt-5.6-terra", 2.00, 12.00, "STANDARD"),
    ("gpt-5.6-sol", 4.00, 20.00, "PREMIUM"),
]
PROFILE = {
    "AI Ops Investigator": ((2200, 4200), (250, 650), (1, 4), [0.72, 0.23, 0.05], (4000, 9500)),
    "Enterprise Knowledge Copilot": (
        (4500, 11500),
        (350, 900),
        (1, 5),
        [0.58, 0.34, 0.08],
        (4500, 10000),
    ),
    "Customer Support Assistant": (
        (700, 2200),
        (120, 420),
        (3, 12),
        [0.86, 0.12, 0.02],
        (1000, 3500),
    ),
    "Data Analyst Copilot": ((2800, 7200), (500, 1600), (1, 5), [0.44, 0.42, 0.14], (5000, 12500)),
    "Developer Assistant": ((2500, 9500), (600, 2200), (1, 7), [0.36, 0.41, 0.23], (4500, 12000)),
}
TEAM_WEIGHTS = {
    "Data Platform": [0.24, 0.18, 0.03, 0.42, 0.13],
    "AI Enablement": [0.30, 0.25, 0.05, 0.22, 0.18],
    "FP&A": [0.05, 0.20, 0.03, 0.64, 0.08],
    "Risk Analytics": [0.10, 0.26, 0.02, 0.54, 0.08],
    "Sales Operations": [0.05, 0.18, 0.28, 0.43, 0.06],
    "Revenue Intelligence": [0.04, 0.15, 0.20, 0.54, 0.07],
    "Process Excellence": [0.17, 0.20, 0.12, 0.45, 0.06],
    "Supply Analytics": [0.14, 0.18, 0.08, 0.53, 0.07],
    "Customer Care": [0.03, 0.19, 0.70, 0.06, 0.02],
    "Knowledge Operations": [0.04, 0.53, 0.34, 0.07, 0.02],
    "Product Analytics": [0.05, 0.18, 0.07, 0.55, 0.15],
    "Developer Experience": [0.04, 0.10, 0.03, 0.18, 0.65],
}


def main():
    rng = random.Random(SEED)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    with engine.begin() as c:
        for table in ["usage_events", "users", "teams", "business_units", "use_cases", "models"]:
            c.execute(text(f"TRUNCATE TABLE finops.{table} RESTART IDENTITY CASCADE;"))
        bu_ids = {}
        for n, b in BUS:
            bu_ids[n] = c.execute(
                text(
                    "INSERT INTO finops.business_units(business_unit_name,monthly_budget_usd) VALUES(:n,:b) RETURNING business_unit_id"
                ),
                {"n": n, "b": b},
            ).scalar_one()
        team_ids = {}
        for t, bu, b in TEAMS:
            team_ids[t] = c.execute(
                text(
                    "INSERT INTO finops.teams(business_unit_id,team_name,monthly_budget_usd) VALUES(:bu,:t,:b) RETURNING team_id"
                ),
                {"bu": bu_ids[bu], "t": t, "b": b},
            ).scalar_one()
        use_ids = {}
        for u, d, b in USES:
            use_ids[u] = c.execute(
                text(
                    "INSERT INTO finops.use_cases(use_case_name,description,monthly_budget_usd) VALUES(:u,:d,:b) RETURNING use_case_id"
                ),
                {"u": u, "d": d, "b": b},
            ).scalar_one()
        model_ids = {}
        costs = {}
        for m, ic, oc, tier in MODELS:
            model_ids[m] = c.execute(
                text(
                    "INSERT INTO finops.models(model_name,input_cost_per_million,output_cost_per_million,model_tier) VALUES(:m,:ic,:oc,:tier) RETURNING model_id"
                ),
                {"m": m, "ic": ic, "oc": oc, "tier": tier},
            ).scalar_one()
            costs[m] = (ic, oc)

        users = []
        uid = 1
        for team, bu, _ in TEAMS:
            for _ in range(25):
                c.execute(
                    text("INSERT INTO finops.users(user_id,team_id,display_name) VALUES(:u,:t,:n)"),
                    {"u": uid, "t": team_ids[team], "n": f"User {uid:03d}"},
                )
                users.append((uid, team, bu))
                uid += 1

        rows = []
        for offset in range(DAYS - 1, -1, -1):
            day = now - timedelta(days=offset)
            weekend = day.weekday() >= 5
            for uid, team, bu in users:
                if rng.random() > (0.24 if weekend else 0.63):
                    continue
                uidx = rng.choices(range(5), weights=TEAM_WEIGHTS[team], k=1)[0]
                uname = USES[uidx][0]
                ir, orr, rr, mw, lat = PROFILE[uname]
                count = rng.randint(*rr)
                recent7 = offset <= 6
                recent14 = offset <= 13
                if (
                    recent7
                    and team in {"FP&A", "Risk Analytics"}
                    and uname == "Data Analyst Copilot"
                ):
                    count = math.ceil(count * 1.8)
                if recent7 and team == "Customer Care" and uname == "Customer Support Assistant":
                    count = math.ceil(count * 1.6)
                for _ in range(count):
                    weights = list(mw)
                    if recent14 and team == "Developer Experience":
                        weights = [0.18, 0.32, 0.50]
                    midx = rng.choices(range(3), weights=weights, k=1)[0]
                    mname = MODELS[midx][0]
                    inp = rng.randint(*ir)
                    out = rng.randint(*orr)
                    if recent7 and uname == "Enterprise Knowledge Copilot" and rng.random() < 0.28:
                        inp = int(inp * 1.7)
                    rp = 0.13 if recent7 and team == "Process Excellence" else 0.035
                    retry = rng.choice([1, 1, 1, 2]) if rng.random() < rp else 0
                    success = rng.random() < (0.985 - retry * 0.02)
                    latency = int(rng.randint(*lat) * (1 + 0.14 * retry))
                    ic, oc = costs[mname]
                    cost = inp / 1_000_000 * ic + out / 1_000_000 * oc
                    ts = day.replace(
                        hour=rng.randint(7, 22),
                        minute=rng.randint(0, 59),
                        second=rng.randint(0, 59),
                    )
                    rows.append(
                        dict(
                            occurred_at=ts,
                            user_id=uid,
                            team_id=team_ids[team],
                            business_unit_id=bu_ids[bu],
                            use_case_id=use_ids[uname],
                            model_id=model_ids[mname],
                            input_tokens=inp,
                            output_tokens=out,
                            latency_ms=latency,
                            retry_count=retry,
                            success=success,
                            estimated_cost_usd=round(cost, 8),
                        )
                    )
        sql = text("""INSERT INTO finops.usage_events(occurred_at,user_id,team_id,business_unit_id,use_case_id,model_id,input_tokens,output_tokens,latency_ms,retry_count,success,estimated_cost_usd)
                    VALUES(:occurred_at,:user_id,:team_id,:business_unit_id,:use_case_id,:model_id,:input_tokens,:output_tokens,:latency_ms,:retry_count,:success,:estimated_cost_usd)""")
        for i in range(0, len(rows), 5000):
            c.execute(sql, rows[i : i + 5000])
    print("GENAI FINOPS DATASET")
    print("=" * 72)
    print("users            : 300")
    print("teams            : 12")
    print("business units   : 6")
    print("use cases        : 5")
    print("models           : 3")
    print("history days     : 120")
    print(f"usage events     : {len(rows)}")
    print("status           : GENERATED")


if __name__ == "__main__":
    main()
