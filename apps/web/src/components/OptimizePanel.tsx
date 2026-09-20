"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import styles from "./OptimizePanel.module.css";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

type Options = {
  business_units: string[];
  teams: string[];
  use_cases: string[];
  models: string[];
};

type Recommendation = {
  rule_id: string;
  category: string;
  priority: "HIGH" | "MEDIUM" | "LOW";
  title: string;
  observation: string;
  diagnostic: string;
  recommendation: string;
  estimated_impact: string;
  estimated_savings_usd: number;
  confidence: string;
  metric_name: string;
  metric_value: number;
  threshold: number;
};

type OptimizeResponse = {
  generated_at: string;
  scope: {
    days: number;
    business_unit: string | null;
    team: string | null;
    use_case: string | null;
    model: string | null;
  };
  metrics: {
    cost_usd: number;
    input_tokens: number;
    output_tokens: number;
    requests: number;
    avg_latency_ms: number;
    retry_rate_pct: number;
    success_rate_pct: number;
    cost_per_request: number;
  };
  summary: {
    recommendation_count: number;
    current_cost_usd: number;
    estimated_savings_usd: number;
    projected_cost_usd: number;
    estimated_savings_pct: number;
  };
  recommendations: Recommendation[];
  methodology: {
    type: string;
    llm_used: boolean;
    automatic_changes: boolean;
    note: string;
  };
};

function money(value: number) {
  return `$${value.toFixed(2)}`;
}

function compact(value: number) {
  return new Intl.NumberFormat("fr-FR", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(value);
}

export default function OptimizePanel() {
  const [days, setDays] = useState("30");
  const [businessUnit, setBusinessUnit] = useState("");
  const [team, setTeam] = useState("");
  const [useCase, setUseCase] = useState("");
  const [model, setModel] = useState("");
  const [options, setOptions] = useState<Options | null>(null);
  const [data, setData] = useState<OptimizeResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadOptions = useCallback(async () => {
    const response = await fetch(`${API_BASE}/api/v1/finops/options`);
    if (!response.ok) {
      throw new Error(`Options API ${response.status}`);
    }
    setOptions(await response.json());
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const params = new URLSearchParams({ days });
      if (businessUnit) params.set("business_unit", businessUnit);
      if (team) params.set("team", team);
      if (useCase) params.set("use_case", useCase);
      if (model) params.set("model", model);

      const response = await fetch(
        `${API_BASE}/api/v1/optimize/recommendations?${params.toString()}`,
      );
      if (!response.ok) {
        throw new Error(`Optimize API ${response.status}`);
      }

      setData(await response.json());
    } catch (currentError) {
      setError(
        currentError instanceof Error
          ? currentError.message
          : "Erreur inconnue pendant l'optimisation.",
      );
    } finally {
      setLoading(false);
    }
  }, [businessUnit, days, model, team, useCase]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadOptions().catch((currentError) => {
        setError(
          currentError instanceof Error
            ? currentError.message
            : "Impossible de charger les filtres.",
        );
      });
    }, 0);

    return () => window.clearTimeout(timer);
  }, [loadOptions]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void load();
    }, 0);

    return () => window.clearTimeout(timer);
  }, [load]);

  const totalTokens = useMemo(() => {
    if (!data) return 0;
    return data.metrics.input_tokens + data.metrics.output_tokens;
  }, [data]);

  return (
    <section className={styles.root}>
      <div className={styles.hero}>
        <div>
          <p className={styles.eyebrow}>DETERMINISTIC OPTIMIZATION ENGINE</p>
          <h2>OPTIMIZE</h2>
          <p className={styles.subtitle}>
            Observation → diagnostic → recommandation → impact estimé.
          </p>
        </div>

        <div className={styles.badges}>
          <span>NO LLM</span>
          <span>READ ONLY</span>
          <span>WHAT-IF</span>
        </div>
      </div>

      <div className={styles.filters}>
        <label>
          <span>PERIOD</span>
          <select value={days} onChange={(event) => setDays(event.target.value)}>
            <option value="7">7 days</option>
            <option value="30">30 days</option>
            <option value="60">60 days</option>
            <option value="120">120 days</option>
          </select>
        </label>

        <label>
          <span>BUSINESS UNIT</span>
          <select
            value={businessUnit}
            onChange={(event) => setBusinessUnit(event.target.value)}
          >
            <option value="">All</option>
            {options?.business_units.map((item) => (
              <option key={item}>{item}</option>
            ))}
          </select>
        </label>

        <label>
          <span>TEAM</span>
          <select value={team} onChange={(event) => setTeam(event.target.value)}>
            <option value="">All</option>
            {options?.teams.map((item) => (
              <option key={item}>{item}</option>
            ))}
          </select>
        </label>

        <label>
          <span>USE CASE</span>
          <select
            value={useCase}
            onChange={(event) => setUseCase(event.target.value)}
          >
            <option value="">All</option>
            {options?.use_cases.map((item) => (
              <option key={item}>{item}</option>
            ))}
          </select>
        </label>

        <label>
          <span>MODEL</span>
          <select value={model} onChange={(event) => setModel(event.target.value)}>
            <option value="">All</option>
            {options?.models.map((item) => (
              <option key={item}>{item}</option>
            ))}
          </select>
        </label>
      </div>

      {error ? <div className={styles.error}>{error}</div> : null}

      <div className={styles.kpis}>
        <article>
          <span>CURRENT COST</span>
          <strong>{money(data?.summary.current_cost_usd ?? 0)}</strong>
          <small>{days} days</small>
        </article>

        <article>
          <span>POTENTIAL SAVINGS</span>
          <strong>{money(data?.summary.estimated_savings_usd ?? 0)}</strong>
          <small>{data?.summary.estimated_savings_pct ?? 0}% simulated</small>
        </article>

        <article>
          <span>PROJECTED COST</span>
          <strong>{money(data?.summary.projected_cost_usd ?? 0)}</strong>
          <small>after simulated optimizations</small>
        </article>

        <article>
          <span>RECOMMENDATIONS</span>
          <strong>{data?.summary.recommendation_count ?? 0}</strong>
          <small>deterministic rules</small>
        </article>

        <article>
          <span>TOKENS</span>
          <strong>{compact(totalTokens)}</strong>
          <small>{compact(data?.metrics.requests ?? 0)} requests</small>
        </article>

        <article>
          <span>AVG LATENCY</span>
          <strong>{((data?.metrics.avg_latency_ms ?? 0) / 1000).toFixed(2)} s</strong>
          <small>selected scope</small>
        </article>
      </div>

      <div className={styles.method}>
        <div>
          <span className={styles.methodLabel}>METHOD</span>
          <strong>DETERMINISTIC_RULES</strong>
        </div>
        <p>
          {data?.methodology.note ??
            "Aucune modification n'est appliquée automatiquement."}
        </p>
      </div>

      <div className={styles.sectionHeader}>
        <div>
          <h3>OPTIMIZATION BACKLOG</h3>
          <p>Les règles sont déclenchées uniquement lorsque leur seuil est dépassé.</p>
        </div>
        <button onClick={() => void load()} disabled={loading}>
          {loading ? "ANALYSE..." : "RECALCULER"}
        </button>
      </div>

      <div className={styles.cards}>
        {!loading && data?.recommendations.length === 0 ? (
          <div className={styles.empty}>
            Aucun seuil d’optimisation n’est dépassé sur le scope sélectionné.
          </div>
        ) : null}

        {data?.recommendations.map((item) => (
          <article className={styles.card} key={item.rule_id}>
            <div className={styles.cardTop}>
              <div>
                <span className={`${styles.priority} ${styles[item.priority.toLowerCase()]}`}>
                  {item.priority}
                </span>
                <span className={styles.category}>{item.category}</span>
              </div>
              <code>{item.rule_id}</code>
            </div>

            <h4>{item.title}</h4>

            <div className={styles.flow}>
              <div>
                <span>OBSERVATION</span>
                <p>{item.observation}</p>
              </div>
              <div>
                <span>DIAGNOSTIC</span>
                <p>{item.diagnostic}</p>
              </div>
              <div>
                <span>ACTION</span>
                <p>{item.recommendation}</p>
              </div>
              <div>
                <span>ESTIMATED IMPACT</span>
                <p>{item.estimated_impact}</p>
              </div>
            </div>

            <div className={styles.cardFooter}>
              <span>
                Metric: <b>{item.metric_name}</b> = {item.metric_value}
              </span>
              <span>
                Threshold: <b>{item.threshold}</b>
              </span>
              <span>
                Confidence: <b>{item.confidence}</b>
              </span>
              <span>
                Saving: <b>{money(item.estimated_savings_usd)}</b>
              </span>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
