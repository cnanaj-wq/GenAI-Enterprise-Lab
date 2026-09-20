"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_FASTAPI_URL ?? "http://127.0.0.1:8000";

type Check = {
  check_id: number;
  check_name: string;
  started_at: string;
  finished_at: string;
  duration_ms: number;
  status: "PASS" | "FAIL" | "WARNING";
  error_message?: string | null;
};

type Pipeline = {
  pipeline_id: string;
  source_type: "SYNTHETIC" | "REAL_LOCAL" | "GITHUB_ACTIONS";
  branch: string;
  commit_sha: string;
  commit_message: string;
  triggered_by: string;
  trigger_type: string;
  push_at?: string | null;
  started_at: string;
  finished_at: string;
  duration_ms: number;
  status: "PASS" | "FAIL" | "WARNING";
  checks: Check[];
};

type RuntimeComponent = {
  status: "HEALTHY" | "DOWN";
  port: number;
};

type HealthSummary = {
  generated_at: string;
  overall: "HEALTHY" | "WARNING" | "CRITICAL";
  git: {
    branch: string;
    short_sha?: string | null;
    commit_message?: string | null;
    commit_at?: string | null;
    working_tree_files: number;
    working_tree_dirty: boolean;
    ahead: number;
    behind: number;
    remote_commit_at?: string | null;
    sync_status: string;
    note: string;
  };
  runtime: Record<string, RuntimeComponent>;
  stats: {
    pipelines_7d: number;
    success_rate_7d: number;
    avg_duration_30d_ms: number;
    last_pipeline_at?: string | null;
  };
  latest_pipeline?: Pipeline | null;
  alerts: Array<{
    severity: "WARNING" | "CRITICAL";
    code: string;
    title: string;
    message: string;
    detected_at: string;
  }>;
};

function time(iso?: string | null) {
  if (!iso) return "—";
  return new Intl.DateTimeFormat("fr-FR", {
    dateStyle: "short",
    timeStyle: "medium",
  }).format(new Date(iso));
}

function duration(ms?: number | null) {
  if (ms === undefined || ms === null) return "—";
  if (ms < 1000) return `${ms} ms`;
  return `${(ms / 1000).toFixed(2)} s`;
}

function badge(status: string) {
  if (status === "PASS" || status === "HEALTHY" || status === "SYNCED") {
    return "bg-emerald-500/15 text-emerald-300";
  }
  if (status === "WARNING" || status === "DIRTY" || status === "PUSH_REQUIRED") {
    return "bg-amber-500/15 text-amber-300";
  }
  if (
    status === "FAIL" ||
    status === "CRITICAL" ||
    status === "DOWN" ||
    status === "BEHIND"
  ) {
    return "bg-red-500/15 text-red-300";
  }
  return "bg-slate-700 text-slate-300";
}

export default function ProjectHealthPanel() {
  const [summary, setSummary] = useState<HealthSummary | null>(null);
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [summaryResponse, pipelineResponse] = await Promise.all([
        fetch(`${API_BASE}/api/v1/project-health/summary`, { cache: "no-store" }),
        fetch(`${API_BASE}/api/v1/project-health/pipelines?limit=40`, {
          cache: "no-store",
        }),
      ]);

      if (!summaryResponse.ok) {
        throw new Error(`summary HTTP ${summaryResponse.status}`);
      }
      if (!pipelineResponse.ok) {
        throw new Error(`pipelines HTTP ${pipelineResponse.status}`);
      }

      const summaryPayload = (await summaryResponse.json()) as HealthSummary;
      const pipelinePayload = (await pipelineResponse.json()) as {
        count: number;
        items: Pipeline[];
      };

      setSummary(summaryPayload);
      setPipelines(pipelinePayload.items);
      setSelectedIndex((current) =>
        pipelinePayload.items.length === 0
          ? 0
          : Math.min(current, pipelinePayload.items.length - 1)
      );
      setError(null);
      setLastRefresh(new Date());
    } catch (refreshError) {
      setError(
        refreshError instanceof Error ? refreshError.message : String(refreshError)
      );
    }
  }, []);

  useEffect(() => {
    const initialTimer = window.setTimeout(() => {
      void refresh();
    }, 0);

    const interval = window.setInterval(() => {
      void refresh();
    }, 10_000);

    return () => {
      window.clearTimeout(initialTimer);
      window.clearInterval(interval);
    };
  }, [refresh]);

  const currentPipeline = pipelines[selectedIndex] ?? null;
  const healthyRuntime = useMemo(
    () =>
      summary
        ? Object.values(summary.runtime).filter(
            (component) => component.status === "HEALTHY"
          ).length
        : 0,
    [summary]
  );

  if (!summary) {
    return (
      <section className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6">
        <h2 className="font-semibold">PROJECT HEALTH</h2>
        <p className="mt-2 text-sm text-slate-500">
          {error ?? "Chargement de la supervision du projet..."}
        </p>
      </section>
    );
  }

  return (
    <section className="space-y-5">
      <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="text-xs font-semibold uppercase tracking-[0.2em] text-cyan-400">
              CI/CD Control Tower
            </div>
            <h2 className="mt-1 text-xl font-semibold">PROJECT HEALTH</h2>
            <p className="mt-1 text-xs text-slate-400">
              Source code · Quality gates · Runtime · Delivery history · Alerts
            </p>
          </div>

          <div className="text-right">
            <span
              className={`rounded-full px-3 py-1 text-xs font-semibold ${badge(
                summary.overall
              )}`}
            >
              ● {summary.overall}
            </span>
            <div className="mt-2 font-mono text-xs text-slate-500">
              Last refresh: {lastRefresh ? time(lastRefresh.toISOString()) : "—"}
            </div>
          </div>
        </div>

        {error && (
          <div className="mt-4 rounded-xl border border-red-900 bg-red-950/40 px-4 py-3 text-sm text-red-300">
            {error}
          </div>
        )}
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <HealthCard
          label="Overall"
          value={summary.overall}
          detail={`${summary.alerts.length} alert(s)`}
          status={summary.overall}
        />
        <HealthCard
          label="Git Sync"
          value={summary.git.sync_status}
          detail={`${summary.git.ahead} ahead / ${summary.git.behind} behind`}
          status={summary.git.sync_status}
        />
        <HealthCard
          label="CI Success 7d"
          value={`${summary.stats.success_rate_7d.toFixed(1)} %`}
          detail={`${summary.stats.pipelines_7d} pipeline(s)`}
          status={summary.stats.success_rate_7d >= 90 ? "HEALTHY" : "WARNING"}
        />
        <HealthCard
          label="Runtime"
          value={`${healthyRuntime}/4`}
          detail="services healthy"
          status={healthyRuntime === 4 ? "HEALTHY" : "CRITICAL"}
        />
      </div>

      <div className="grid gap-5 xl:grid-cols-[1fr_1fr]">
        <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
          <h3 className="font-semibold">SOURCE CODE</h3>
          <div className="mt-4 space-y-3 text-sm">
            <Line label="Branch" value={summary.git.branch} mono />
            <Line label="Last commit" value={summary.git.short_sha ?? "—"} mono />
            <Line
              label="Commit message"
              value={summary.git.commit_message ?? "—"}
            />
            <Line label="Commit date" value={time(summary.git.commit_at)} />
            <Line
              label="Local modifications"
              value={String(summary.git.working_tree_files)}
            />
            <Line
              label="Remote sync commit"
              value={time(summary.git.remote_commit_at)}
            />
            <Line
              label="Ahead / Behind"
              value={`${summary.git.ahead} / ${summary.git.behind}`}
            />
          </div>
          <p className="mt-4 text-xs text-slate-600">{summary.git.note}</p>
        </div>

        <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
          <h3 className="font-semibold">RUNTIME COMPONENTS</h3>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {Object.entries(summary.runtime).map(([name, component]) => (
              <div
                key={name}
                className="rounded-xl border border-slate-800 bg-slate-950/50 p-4"
              >
                <div className="flex items-center justify-between gap-3">
                  <span className="font-medium capitalize">{name}</span>
                  <span
                    className={`rounded-full px-2 py-1 text-xs font-semibold ${badge(
                      component.status
                    )}`}
                  >
                    {component.status}
                  </span>
                </div>
                <div className="mt-2 font-mono text-xs text-slate-500">
                  :{component.port}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="font-semibold">ALERTS</h3>
            <p className="text-xs text-slate-400">
              Alertes calculées à partir de Git, CI et des composants runtime.
            </p>
          </div>
          <button
            type="button"
            onClick={() => void refresh()}
            className="rounded-xl border border-slate-700 px-4 py-2 text-xs text-slate-300"
          >
            Refresh now
          </button>
        </div>

        {summary.alerts.length === 0 ? (
          <div className="mt-4 rounded-xl border border-emerald-900/50 bg-emerald-950/10 px-4 py-4 text-sm text-emerald-300">
            Aucun signal critique ou warning actif.
          </div>
        ) : (
          <div className="mt-4 space-y-3">
            {summary.alerts.map((alert) => (
              <div
                key={`${alert.code}-${alert.detected_at}`}
                className={`rounded-xl border px-4 py-3 ${
                  alert.severity === "CRITICAL"
                    ? "border-red-900 bg-red-950/30"
                    : "border-amber-900 bg-amber-950/20"
                }`}
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="font-medium">{alert.title}</div>
                  <span
                    className={`rounded-full px-2 py-1 text-xs font-semibold ${badge(
                      alert.severity
                    )}`}
                  >
                    {alert.severity}
                  </span>
                </div>
                <div className="mt-1 text-sm text-slate-400">{alert.message}</div>
                <div className="mt-2 font-mono text-xs text-slate-600">
                  {time(alert.detected_at)} · {alert.code}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="font-semibold">DELIVERY HISTORY</h3>
            <p className="text-xs text-slate-400">
              Carrousel horodaté des pipelines et quality gates.
            </p>
          </div>
          <div className="font-mono text-xs text-slate-500">
            {pipelines.length === 0 ? "0 / 0" : `${selectedIndex + 1} / ${pipelines.length}`}
          </div>
        </div>

        {currentPipeline ? (
          <div className="mt-5">
            <div className="rounded-2xl border border-slate-700 bg-slate-950/60 p-5">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <span
                      className={`rounded-full px-2 py-1 text-xs font-semibold ${badge(
                        currentPipeline.status
                      )}`}
                    >
                      {currentPipeline.status}
                    </span>
                    <span className="rounded-full bg-violet-500/15 px-2 py-1 text-xs font-semibold text-violet-300">
                      {currentPipeline.source_type}
                    </span>
                    <span className="rounded-full bg-slate-800 px-2 py-1 text-xs text-slate-400">
                      {currentPipeline.trigger_type}
                    </span>
                  </div>
                  <div className="mt-3 text-lg font-semibold">
                    {currentPipeline.commit_message}
                  </div>
                  <div className="mt-1 font-mono text-xs text-slate-500">
                    {currentPipeline.commit_sha.slice(0, 8)} · {currentPipeline.branch}
                  </div>
                </div>

                <div className="text-right">
                  <div className="text-xl font-semibold">
                    {duration(currentPipeline.duration_ms)}
                  </div>
                  <div className="text-xs text-slate-500">pipeline total</div>
                </div>
              </div>

              <div className="mt-5 grid gap-3 text-xs text-slate-400 sm:grid-cols-3">
                <div>
                  Push
                  <div className="mt-1 font-mono text-slate-200">
                    {time(currentPipeline.push_at)}
                  </div>
                </div>
                <div>
                  Started
                  <div className="mt-1 font-mono text-slate-200">
                    {time(currentPipeline.started_at)}
                  </div>
                </div>
                <div>
                  Finished
                  <div className="mt-1 font-mono text-slate-200">
                    {time(currentPipeline.finished_at)}
                  </div>
                </div>
              </div>

              <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                {currentPipeline.checks.map((check) => (
                  <div
                    key={check.check_id}
                    className="rounded-xl border border-slate-800 bg-slate-900/70 p-4"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-semibold">{check.check_name}</span>
                      <span
                        className={`rounded-full px-2 py-1 text-xs font-semibold ${badge(
                          check.status
                        )}`}
                      >
                        {check.status}
                      </span>
                    </div>
                    <div className="mt-2 font-mono text-xs text-slate-400">
                      {duration(check.duration_ms)}
                    </div>
                    <div className="mt-1 font-mono text-[11px] text-slate-600">
                      {time(check.started_at)}
                    </div>
                    {check.error_message && (
                      <div className="mt-3 text-xs text-red-300">
                        {check.error_message}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>

            <div className="mt-4 flex items-center justify-between gap-3">
              <button
                type="button"
                onClick={() =>
                  setSelectedIndex((current) =>
                    Math.min(current + 1, pipelines.length - 1)
                  )
                }
                disabled={selectedIndex >= pipelines.length - 1}
                className="rounded-xl border border-slate-700 px-4 py-2 text-sm text-slate-300 disabled:opacity-30"
              >
                ← Plus ancien
              </button>
              <button
                type="button"
                onClick={() =>
                  setSelectedIndex((current) => Math.max(current - 1, 0))
                }
                disabled={selectedIndex === 0}
                className="rounded-xl border border-slate-700 px-4 py-2 text-sm text-slate-300 disabled:opacity-30"
              >
                Plus récent →
              </button>
            </div>
          </div>
        ) : (
          <div className="mt-5 rounded-xl border border-dashed border-slate-700 px-4 py-10 text-center text-sm text-slate-500">
            Aucun pipeline disponible.
          </div>
        )}

        <div className="mt-4 text-xs text-slate-600">
          SYNTHETIC = historique pédagogique simulé. Les pipelines GitHub Actions réels
          seront identifiés séparément comme GITHUB_ACTIONS.
        </div>
      </div>
    </section>
  );
}

function HealthCard({
  label,
  value,
  detail,
  status,
}: {
  label: string;
  value: string;
  detail: string;
  status: string;
}) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-4">
      <div className="flex items-center justify-between gap-2">
        <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
        <span className={`h-2.5 w-2.5 rounded-full ${
          badge(status).includes("emerald")
            ? "bg-emerald-400"
            : badge(status).includes("amber")
              ? "bg-amber-400"
              : "bg-red-400"
        }`} />
      </div>
      <div className="mt-2 text-2xl font-semibold">{value}</div>
      <div className="mt-1 text-xs text-slate-400">{detail}</div>
    </div>
  );
}

function Line({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-slate-800/70 pb-2">
      <span className="text-slate-500">{label}</span>
      <span className={`text-right text-slate-200 ${mono ? "font-mono" : ""}`}>
        {value}
      </span>
    </div>
  );
}
