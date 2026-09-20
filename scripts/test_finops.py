from __future__ import annotations

import httpx

API = "http://127.0.0.1:8000"


def main():
    o = httpx.get(f"{API}/api/v1/finops/options", timeout=10)
    o.raise_for_status()
    p = o.json()
    r = httpx.get(f"{API}/api/v1/finops/overview", params={"days": 120}, timeout=20)
    r.raise_for_status()
    x = r.json()
    print("GENAI FINOPS")
    print("=" * 72)
    print(f"business units : {len(p['business_units'])}")
    print(f"teams          : {len(p['teams'])}")
    print(f"use cases      : {len(p['use_cases'])}")
    print(f"models         : {len(p['models'])}")
    print(f"requests       : {x['kpis']['requests']}")
    print(f"active users   : {x['kpis']['active_users']}")
    print(f"tokens         : {x['kpis']['total_tokens']}")
    print(f"cost USD       : {float(x['kpis']['cost_usd']):.4f}")
    print(f"alerts         : {len(x['alerts'])}")
    assert len(p["business_units"]) == 6
    assert len(p["teams"]) == 12
    assert len(p["use_cases"]) == 5
    assert len(p["models"]) == 3
    assert x["kpis"]["requests"] > 0
    assert len(x["time_series"]) > 0
    print("\nSTEP 1.11 GENAI FINOPS: VALIDATED")


if __name__ == "__main__":
    main()
