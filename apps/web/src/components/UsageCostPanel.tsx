"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_FASTAPI_URL ?? "http://127.0.0.1:8000";

type Options = { business_units:string[]; teams:string[]; use_cases:string[]; models:string[] };
type Overview = {
  generated_at:string; days:number;
  kpis:{requests:number;active_users:number;input_tokens:number;output_tokens:number;total_tokens:number;cost_usd:number;cost_per_request:number;tokens_per_request:number;avg_latency_ms:number;success_rate:number;retry_rate:number};
  time_series:Array<{day:string;requests:number;total_tokens:number;cost_usd:number}>;
  by_use_case:Array<{name:string;requests:number;total_tokens:number;cost_usd:number;cost_per_request:number;avg_latency_ms:number}>;
  by_model:Array<{name:string;tier:string;requests:number;total_tokens:number;cost_usd:number}>;
  by_business_unit:Array<{name:string;requests:number;active_users:number;total_tokens:number;cost_usd:number}>;
  top_users:Array<{user_name:string;team_name:string;business_unit_name:string;requests:number;total_tokens:number;cost_usd:number}>;
  budgets:Array<{name:string;budget_usd:number;spend_usd:number}>;
  alerts:Array<{severity:"WARNING"|"CRITICAL";code:string;title:string;message:string}>;
};

const compact=(v:number)=>new Intl.NumberFormat("fr-FR",{notation:"compact",maximumFractionDigits:1}).format(v);
const money=(v:number)=>`$${Number(v||0).toFixed(2)}`;
const ms=(v:number)=>v<1000?`${Math.round(v)} ms`:`${(v/1000).toFixed(2)} s`;

export default function UsageCostPanel(){
  const [options,setOptions]=useState<Options|null>(null);
  const [overview,setOverview]=useState<Overview|null>(null);
  const [days,setDays]=useState(30);
  const [businessUnit,setBusinessUnit]=useState("");
  const [team,setTeam]=useState("");
  const [useCase,setUseCase]=useState("");
  const [model,setModel]=useState("");
  const [error,setError]=useState<string|null>(null);

  const load=useCallback(async()=>{
    try{
      const params=new URLSearchParams({days:String(days)});
      if(businessUnit) params.set("business_unit",businessUnit);
      if(team) params.set("team",team);
      if(useCase) params.set("use_case",useCase);
      if(model) params.set("model",model);

      const [o,r]=await Promise.all([
        fetch(`${API_BASE}/api/v1/finops/options`,{cache:"no-store"}),
        fetch(`${API_BASE}/api/v1/finops/overview?${params}`,{cache:"no-store"})
      ]);
      if(!o.ok) throw new Error(`Options HTTP ${o.status}`);
      if(!r.ok) throw new Error(`Overview HTTP ${r.status}`);
      setOptions(await o.json() as Options);
      setOverview(await r.json() as Overview);
      setError(null);
    }catch(e){setError(e instanceof Error?e.message:String(e))}
  },[days,businessUnit,team,useCase,model]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void load();
    }, 0);

    return () => window.clearTimeout(timer);
  }, [load]);

  const maxDaily=useMemo(()=>Math.max(...(overview?.time_series.map(r=>Number(r.cost_usd))??[1]),1),[overview]);

  if(!overview||!options){
    return <section className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6">
      <h2 className="font-semibold">USAGE & COST</h2>
      <p className="mt-2 text-sm text-slate-500">{error??"Chargement du cockpit GenAI FinOps..."}</p>
    </section>
  }

  return <section className="space-y-5">
    <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-xs font-semibold uppercase tracking-[0.2em] text-cyan-400">GenAI FinOps & Usage Governance</div>
          <h2 className="mt-1 text-xl font-semibold">USAGE & COST</h2>
          <p className="mt-1 text-xs text-slate-400">300 users · 12 teams · 6 BU · 5 use cases · 3 models · 120 days</p>
        </div>
        <div className="font-mono text-xs text-slate-500">{new Date(overview.generated_at).toLocaleString("fr-FR")}</div>
      </div>

      <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-5">
        <Select label="Period" value={String(days)} onChange={v=>setDays(Number(v))} options={[["7","7 days"],["30","30 days"],["60","60 days"],["120","120 days"]]}/>
        <Select label="Business Unit" value={businessUnit} onChange={setBusinessUnit} options={[["","All"],...options.business_units.map(v=>[v,v])]}/>
        <Select label="Team" value={team} onChange={setTeam} options={[["","All"],...options.teams.map(v=>[v,v])]}/>
        <Select label="Use Case" value={useCase} onChange={setUseCase} options={[["","All"],...options.use_cases.map(v=>[v,v])]}/>
        <Select label="Model" value={model} onChange={setModel} options={[["","All"],...options.models.map(v=>[v,v])]}/>
      </div>
      {error&&<div className="mt-4 rounded-xl border border-red-900 bg-red-950/30 px-4 py-3 text-sm text-red-300">{error}</div>}
    </div>

    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
      <Kpi label="Cost" value={money(Number(overview.kpis.cost_usd))} detail={`${days} days`}/>
      <Kpi label="Tokens" value={compact(Number(overview.kpis.total_tokens))} detail={`${compact(Number(overview.kpis.input_tokens))} in / ${compact(Number(overview.kpis.output_tokens))} out`}/>
      <Kpi label="Requests" value={compact(Number(overview.kpis.requests))} detail={`${overview.kpis.active_users} active users`}/>
      <Kpi label="Cost / Request" value={`$${Number(overview.kpis.cost_per_request).toFixed(4)}`} detail={`${Math.round(Number(overview.kpis.tokens_per_request))} tokens/request`}/>
      <Kpi label="Success Rate" value={`${Number(overview.kpis.success_rate).toFixed(1)} %`} detail={`Retry ${Number(overview.kpis.retry_rate).toFixed(1)} %`}/>
      <Kpi label="Avg Latency" value={ms(Number(overview.kpis.avg_latency_ms))} detail="selected scope"/>
    </div>

    <div className="grid gap-5 xl:grid-cols-[1.3fr_0.7fr]">
      <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
        <h3 className="font-semibold">DAILY COST TREND</h3>
        <p className="mt-1 text-xs text-slate-400">Survole une barre pour voir coût et tokens.</p>
        <div className="mt-5 overflow-x-auto pb-2">
          <div
            className="flex h-60 items-end gap-2 pt-7"
            style={{ minWidth: `${Math.max(overview.time_series.length * 38, 780)}px` }}
          >
            {overview.time_series.map((row) => {
              const cost = Number(row.cost_usd);
              const h = Math.max(4, (cost / maxDaily) * 82);

              return (
                <div
                  key={row.day}
                  className="relative flex h-full min-w-[30px] flex-1 items-end justify-center"
                  title={`${row.day} · ${money(cost)} · ${compact(Number(row.total_tokens))} tokens`}
                >
                  <div
                    className="relative w-full rounded-t bg-cyan-500/70 transition hover:bg-cyan-400"
                    style={{ height: `${h}%` }}
                  >
                    <span className="absolute -top-5 left-1/2 z-10 -translate-x-1/2 whitespace-nowrap font-mono text-[9px] font-semibold text-cyan-200">
                      ${cost.toFixed(2)}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
        <div className="mt-2 flex justify-between font-mono text-[10px] text-slate-600">
          <span>{overview.time_series[0]?.day??"—"}</span>
          <span>{overview.time_series.at(-1)?.day??"—"}</span>
        </div>
      </div>

      <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
        <h3 className="font-semibold">ALERTS</h3>
        <p className="mt-1 text-xs text-slate-400">Alertes du scope courant uniquement · budget · coût · retries · premium model</p>
        <div className="mt-4 max-h-56 space-y-3 overflow-y-auto">
          {overview.alerts.length===0
            ? <div className="rounded-xl border border-emerald-900/50 bg-emerald-950/10 p-4 text-sm text-emerald-300">Aucun signal actif.</div>
            : overview.alerts.map((a,i)=><div key={`${a.code}-${i}`} className={`rounded-xl border p-3 ${a.severity==="CRITICAL"?"border-red-900 bg-red-950/25":"border-amber-900 bg-amber-950/20"}`}>
                <div className="flex items-center justify-between gap-2"><span className="text-sm font-medium">{a.title}</span><span className={a.severity==="CRITICAL"?"text-red-300":"text-amber-300"}>{a.severity}</span></div>
                <div className="mt-1 text-xs text-slate-400">{a.message}</div>
              </div>)}
        </div>
      </div>
    </div>

    <div className="grid gap-5 xl:grid-cols-2">
      <Rank title="COST BY USE CASE" rows={overview.by_use_case.map(r=>({name:r.name,primary:money(Number(r.cost_usd)),secondary:`${compact(Number(r.requests))} req · $${Number(r.cost_per_request).toFixed(4)}/req`}))}/>
      <Rank title="COST BY MODEL" rows={overview.by_model.map(r=>({name:`${r.name} · ${r.tier}`,primary:money(Number(r.cost_usd)),secondary:`${compact(Number(r.requests))} req · ${compact(Number(r.total_tokens))} tokens`}))}/>
    </div>

    <div className="grid gap-5 xl:grid-cols-2">
      <Rank title="COST BY BUSINESS UNIT" rows={overview.by_business_unit.map(r=>({name:r.name,primary:money(Number(r.cost_usd)),secondary:`${r.active_users} users · ${compact(Number(r.requests))} req`}))}/>
      <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
        <h3 className="font-semibold">MONTHLY BUDGETS</h3>
        <div className="mt-4 space-y-4">
          {overview.budgets.map(r=>{
            const pct=Number(r.budget_usd)>0?100*Number(r.spend_usd)/Number(r.budget_usd):0;
            return <div key={r.name}>
              <div className="flex justify-between gap-3 text-sm"><span>{r.name}</span><span className="font-mono text-slate-300">{money(Number(r.spend_usd))} / {money(Number(r.budget_usd))}</span></div>
              <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-800">
                <div className={`h-full rounded-full ${pct>=90?"bg-red-500":pct>=75?"bg-amber-400":"bg-emerald-400"}`} style={{width:`${Math.min(pct,100)}%`}}/>
              </div>
              <div className="mt-1 text-right font-mono text-[10px] text-slate-600">{pct.toFixed(1)} %</div>
            </div>
          })}
        </div>
      </div>
    </div>

    <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
      <h3 className="font-semibold">TOP CONSUMERS</h3>
      <p className="mt-1 text-xs text-slate-400">Coût élevé ≠ mauvaise utilisation : le contexte métier compte.</p>
      <div className="mt-4 overflow-x-auto">
        <table className="min-w-full text-left text-xs">
          <thead className="bg-slate-950/60 text-slate-500"><tr>
            <th className="px-4 py-3">User</th><th className="px-4 py-3">Team</th><th className="px-4 py-3">BU</th>
            <th className="px-4 py-3 text-right">Requests</th><th className="px-4 py-3 text-right">Tokens</th><th className="px-4 py-3 text-right">Cost</th>
          </tr></thead>
          <tbody>{overview.top_users.map((r,i)=><tr key={`${r.user_name}-${r.team_name}`} className={`border-t border-slate-800 ${i%2?"bg-slate-950/25":""}`}>
            <td className="px-4 py-3 font-medium text-slate-200">{r.user_name}</td><td className="px-4 py-3 text-slate-400">{r.team_name}</td><td className="px-4 py-3 text-slate-400">{r.business_unit_name}</td>
            <td className="px-4 py-3 text-right font-mono">{r.requests}</td><td className="px-4 py-3 text-right font-mono">{compact(Number(r.total_tokens))}</td><td className="px-4 py-3 text-right font-mono">{money(Number(r.cost_usd))}</td>
          </tr>)}</tbody>
        </table>
      </div>
    </div>
  </section>
}

function Kpi({label,value,detail}:{label:string;value:string;detail:string}){
  return <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-4"><div className="text-xs uppercase tracking-wide text-slate-500">{label}</div><div className="mt-2 text-2xl font-semibold">{value}</div><div className="mt-1 text-xs text-slate-400">{detail}</div></div>
}
function Select({label,value,onChange,options}:{label:string;value:string;onChange:(v:string)=>void;options:string[][]}){
  return <div><label className="mb-2 block text-xs uppercase tracking-wide text-slate-500">{label}</label>
    <select value={value} onChange={e=>onChange(e.target.value)} className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200 outline-none focus:border-cyan-500">
      {options.map(([v,l])=><option key={`${label}-${v}`} value={v}>{l}</option>)}
    </select></div>
}
function Rank({title,rows}:{title:string;rows:Array<{name:string;primary:string;secondary:string}>}){
  return <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5"><h3 className="font-semibold">{title}</h3><div className="mt-4 space-y-2">
    {rows.map((r,i)=><div key={r.name} className={`flex items-center justify-between gap-4 rounded-xl px-4 py-3 ${i%2?"bg-slate-950/35":"bg-slate-950/15"}`}>
      <div className="min-w-0"><div className="truncate text-sm font-medium">{r.name}</div><div className="mt-1 text-xs text-slate-500">{r.secondary}</div></div>
      <div className="font-mono text-sm font-semibold text-slate-200">{r.primary}</div>
    </div>)}
  </div></div>
}
