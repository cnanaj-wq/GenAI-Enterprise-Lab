"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Background,
  Controls,
  Edge,
  MarkerType,
  MiniMap,
  Node,
  ReactFlow,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

const API_BASE = process.env.NEXT_PUBLIC_FASTAPI_URL ?? "http://127.0.0.1:8000";

type EventPayload = {
  trace_id: string | null;
  span_id: string | null;
  event_type: string;
  occurred_at: string | null;
  sequence_no: number | null;
  event_data: Record<string, unknown> | null;
};

type SpanStatus = "RUNNING" | "SUCCESS" | "ERROR" | "WAITING";
type SpanType =
  | "NODE"
  | "TOOL"
  | "MCP"
  | "DATABASE"
  | "LLM"
  | "EVALUATION"
  | "OTHER";

type SpanView = {
  spanId: string;
  parentSpanId?: string | null;
  name: string;
  spanType: SpanType;
  status: SpanStatus;
  durationMs?: number;
  sequenceNo: number;
};

type Breakdown = {
  total_ms: number;
  total_pct: number;
  mcp_duration_ms?: number;
  mcp_pct?: number;
  llm_duration_ms?: number;
  llm_pct?: number;
  unattributed_ms: number;
  unattributed_pct: number;
  note?: string;
};

type InvestigationStart = {
  run_id: string;
  status: string;
  stream_url: string;
  state_url: string;
};

type LLMMetric = {
  provider: string;
  model: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  estimated_cost_usd: number;
  duration_ms: number;
};

type MCPStatus = {
  mcp: string;
  endpoint?: string;
  protocol_version?: string;
  tool_count?: number;
};

const TYPE_META: Record<
  SpanType,
  { label: string; border: string; bg: string; dot: string }
> = {
  NODE: {
    label: "NODE LangGraph",
    border: "#a855f7",
    bg: "#221332",
    dot: "#c084fc",
  },
  TOOL: {
    label: "TOOL",
    border: "#3b82f6",
    bg: "#10213a",
    dot: "#60a5fa",
  },
  MCP: {
    label: "MCP",
    border: "#06b6d4",
    bg: "#0c2630",
    dot: "#22d3ee",
  },
  DATABASE: {
    label: "DATABASE",
    border: "#f97316",
    bg: "#2b1b0f",
    dot: "#fb923c",
  },
  LLM: {
    label: "LLM",
    border: "#22c55e",
    bg: "#10271a",
    dot: "#4ade80",
  },
  EVALUATION: {
    label: "EVALUATION",
    border: "#eab308",
    bg: "#2b250c",
    dot: "#facc15",
  },
  OTHER: {
    label: "OTHER",
    border: "#64748b",
    bg: "#172033",
    dot: "#94a3b8",
  },
};

function normalizeSpanType(value: unknown): SpanType {
  const normalized = String(value ?? "OTHER").toUpperCase();
  if (
    normalized === "NODE" ||
    normalized === "TOOL" ||
    normalized === "MCP" ||
    normalized === "DATABASE" ||
    normalized === "LLM" ||
    normalized === "EVALUATION"
  ) {
    return normalized;
  }
  return "OTHER";
}

function formatLocalTime(iso?: string | null) {
  if (!iso) return "—";
  return new Intl.DateTimeFormat("fr-FR", {
    dateStyle: "short",
    timeStyle: "medium",
  }).format(new Date(iso));
}

function formatDuration(ms?: number) {
  if (ms === undefined || ms === null) return "—";
  if (ms < 1000) return `${ms} ms`;
  return `${(ms / 1000).toFixed(2)} s`;
}

function statusSymbol(status: SpanStatus) {
  if (status === "SUCCESS") return "✓";
  if (status === "ERROR") return "✕";
  if (status === "RUNNING") return "●";
  return "○";
}

export default function Home() {
  const [prompt, setPrompt] = useState(
    "Pourquoi Sales_Analytics_033 a échoué lors de son dernier reload ?"
  );
  const [applicationName, setApplicationName] = useState("Sales_Analytics_033");
  const [runId, setRunId] = useState<string | null>(null);
  const [traceId, setTraceId] = useState<string | null>(null);
  const [status, setStatus] = useState<"IDLE" | "RUNNING" | "SUCCESS" | "ERROR">(
    "IDLE"
  );
  const [startedAt, setStartedAt] = useState<string | null>(null);
  const [finishedAt, setFinishedAt] = useState<string | null>(null);
  const [events, setEvents] = useState<EventPayload[]>([]);
  const [spans, setSpans] = useState<SpanView[]>([]);
  const [breakdown, setBreakdown] = useState<Breakdown | null>(null);
  const [summary, setSummary] = useState<Record<string, unknown> | null>(null);
  const [diagnosis, setDiagnosis] = useState<string | null>(null);
  const [llmMetric, setLlmMetric] = useState<LLMMetric | null>(null);
  const [mcpStatus, setMcpStatus] = useState<MCPStatus | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const sourceRef = useRef<EventSource | null>(null);

  const refreshMcpStatus = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/api/v1/mcp/status`, {
        cache: "no-store",
      });
      if (!response.ok) {
        setMcpStatus({ mcp: "unhealthy" });
        return;
      }
      setMcpStatus((await response.json()) as MCPStatus);
    } catch {
      setMcpStatus({ mcp: "unhealthy" });
    }
  }, []);

  useEffect(() => {
    void refreshMcpStatus();
  }, [refreshMcpStatus]);

  const resetRun = useCallback(() => {
    sourceRef.current?.close();
    sourceRef.current = null;
    setRunId(null);
    setTraceId(null);
    setStatus("IDLE");
    setStartedAt(null);
    setFinishedAt(null);
    setEvents([]);
    setSpans([]);
    setBreakdown(null);
    setSummary(null);
    setDiagnosis(null);
    setLlmMetric(null);
    setErrorMessage(null);
  }, []);

  const handleEvent = useCallback((event: EventPayload) => {
    setEvents((current) => [...current, event].slice(-300));

    if (event.trace_id) setTraceId(event.trace_id);
    const data = event.event_data ?? {};

    if (event.event_type === "trace_started") {
      setStatus("RUNNING");
      setStartedAt(event.occurred_at);
    }

    if (event.event_type === "span_started") {
      const spanId = String(data.span_id ?? event.span_id ?? "");
      const parentSpanId = data.parent_span_id
        ? String(data.parent_span_id)
        : null;

      setSpans((current) => {
        const without = current.filter((span) => span.spanId !== spanId);
        return [
          ...without,
          {
            spanId,
            parentSpanId,
            name: String(data.name ?? "unknown"),
            spanType: normalizeSpanType(data.span_type),
            status: "RUNNING",
            sequenceNo: Number(data.sequence_no ?? 0),
          },
        ].sort((a, b) => a.sequenceNo - b.sequenceNo);
      });
    }

    if (event.event_type === "span_finished") {
      const spanId = String(data.span_id ?? event.span_id ?? "");
      const nextStatus: SpanStatus =
        String(data.status ?? "SUCCESS") === "SUCCESS" ? "SUCCESS" : "ERROR";

      setSpans((current) =>
        current.map((span) =>
          span.spanId === spanId
            ? {
                ...span,
                status: nextStatus,
                durationMs: Number(data.duration_ms ?? 0),
              }
            : span
        )
      );
    }

    if (event.event_type === "llm_measurement") {
      setLlmMetric(data as unknown as LLMMetric);
    }

    if (event.event_type === "diagnosis_ready") {
      setDiagnosis(String(data.diagnosis ?? ""));
      setLlmMetric(data as unknown as LLMMetric);
    }

    if (event.event_type === "investigation_summary") setSummary(data);

    if (event.event_type === "trace_finished") {
      setFinishedAt(event.occurred_at);
      setStatus(String(data.status ?? "SUCCESS") === "SUCCESS" ? "SUCCESS" : "ERROR");
    }

    if (event.event_type === "execution_breakdown") {
      setBreakdown(data as unknown as Breakdown);
    }

    if (event.event_type === "run_error") {
      setStatus("ERROR");
      setErrorMessage(String(data.error_message ?? "Unknown run error"));
    }
  }, []);

  const startInvestigation = useCallback(async () => {
    resetRun();
    setStatus("RUNNING");
    void refreshMcpStatus();

    const response = await fetch(`${API_BASE}/api/v1/investigations`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prompt,
        application_name: applicationName || null,
      }),
    });

    if (!response.ok) {
      const body = await response.text();
      setStatus("ERROR");
      setErrorMessage(`HTTP ${response.status}: ${body}`);
      return;
    }

    const run = (await response.json()) as InvestigationStart;
    setRunId(run.run_id);

    const source = new EventSource(`${API_BASE}${run.stream_url}`);
    sourceRef.current = source;

    const eventNames = [
      "trace_started",
      "mcp_connected",
      "candidate_selected",
      "span_started",
      "span_finished",
      "mcp_measurement",
      "route_decision",
      "llm_measurement",
      "diagnosis_ready",
      "investigation_summary",
      "trace_finished",
      "execution_breakdown",
      "run_error",
    ];

    for (const eventName of eventNames) {
      source.addEventListener(eventName, (message) => {
        const parsed = JSON.parse((message as MessageEvent).data) as EventPayload;
        handleEvent(parsed);

        if (
          parsed.event_type === "execution_breakdown" ||
          parsed.event_type === "run_error"
        ) {
          source.close();
          sourceRef.current = null;
        }
      });
    }
  }, [applicationName, handleEvent, prompt, refreshMcpStatus, resetRun]);

  const graphNodes = useMemo<Node[]>(() => {
    if (spans.length === 0) {
      return [
        {
          id: "waiting",
          position: { x: 120, y: 50 },
          data: { label: "En attente d'une investigation" },
        },
      ];
    }

    const childrenByParent = new Map<string, SpanView[]>();
    const roots: SpanView[] = [];

    for (const span of spans) {
      if (span.parentSpanId) {
        const children = childrenByParent.get(span.parentSpanId) ?? [];
        children.push(span);
        childrenByParent.set(span.parentSpanId, children);
      } else {
        roots.push(span);
      }
    }

    roots.sort((a, b) => a.sequenceNo - b.sequenceNo);
    for (const children of childrenByParent.values()) {
      children.sort((a, b) => a.sequenceNo - b.sequenceNo);
    }

    const nodes: Node[] = [];
    let y = 35;

    const createNode = (
      span: SpanView,
      x: number,
      yPos: number,
      isChild: boolean
    ): Node => {
      const typeMeta = TYPE_META[span.spanType];
      const borderColor =
        span.status === "ERROR"
          ? "#ef4444"
          : span.status === "RUNNING"
            ? "#f59e0b"
            : typeMeta.border;

      return {
        id: span.spanId,
        position: { x, y: yPos },
        data: {
          label: `${statusSymbol(span.status)} ${typeMeta.label}\n${span.name}\n${formatDuration(span.durationMs)}`,
        },
        style: {
          width: isChild ? 250 : 300,
          minHeight: isChild ? 82 : 94,
          borderRadius: 14,
          borderWidth: 2,
          borderStyle: "solid",
          borderColor,
          background: span.status === "ERROR" ? "#2a1115" : typeMeta.bg,
          color: "#f8fafc",
          padding: 12,
          whiteSpace: "pre-line",
          fontSize: isChild ? 12 : 13,
          fontWeight: 600,
        },
      };
    };

    for (const rootSpan of roots) {
      const children = childrenByParent.get(rootSpan.spanId) ?? [];
      const rootY = y;

      nodes.push(createNode(rootSpan, 60, rootY, false));

      children.forEach((child, childIndex) => {
        nodes.push(createNode(child, 430, rootY + childIndex * 102, true));
      });

      y += Math.max(125, children.length * 102 + 25);
    }

    return nodes;
  }, [spans]);

  const graphEdges = useMemo<Edge[]>(() => {
    const edges: Edge[] = [];
    const roots = spans
      .filter((span) => !span.parentSpanId)
      .sort((a, b) => a.sequenceNo - b.sequenceNo);

    roots.slice(1).forEach((root, index) => {
      const previous = roots[index];
      edges.push({
        id: `root-${previous.spanId}-${root.spanId}`,
        source: previous.spanId,
        target: root.spanId,
        markerEnd: { type: MarkerType.ArrowClosed },
        animated: root.status === "RUNNING",
        style: { stroke: "#64748b" },
      });
    });

    spans
      .filter((span) => span.parentSpanId)
      .forEach((child) => {
        edges.push({
          id: `parent-${child.parentSpanId}-${child.spanId}`,
          source: child.parentSpanId as string,
          target: child.spanId,
          markerEnd: { type: MarkerType.ArrowClosed },
          animated: child.status === "RUNNING",
          style: {
            stroke: TYPE_META[child.spanType].border,
            strokeWidth: 2,
          },
        });
      });

    return edges;
  }, [spans]);

  return (
    <main className="min-h-screen bg-slate-950 px-4 py-6 text-slate-100 md:px-8">
      <div className="mx-auto max-w-[1700px] space-y-5">
        <header className="flex flex-col gap-3 rounded-2xl border border-slate-800 bg-slate-900/70 p-5 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="text-xs font-semibold uppercase tracking-[0.22em] text-cyan-400">
              GenAI Enterprise Lab
            </div>
            <h1 className="mt-1 text-2xl font-semibold">AI Ops Investigator</h1>
            <p className="mt-1 text-sm text-slate-400">
              LangGraph → MCP → Enterprise Tools → PostgreSQL
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`rounded-full px-3 py-1 text-xs font-semibold ${
                mcpStatus?.mcp === "healthy"
                  ? "bg-cyan-500/15 text-cyan-300"
                  : "bg-red-500/15 text-red-300"
              }`}
            >
              MCP ● {mcpStatus?.mcp === "healthy" ? "CONNECTED" : "UNAVAILABLE"}
            </span>

            <span
              className={`rounded-full px-3 py-1 text-xs font-semibold ${
                status === "RUNNING"
                  ? "bg-amber-500/15 text-amber-300"
                  : status === "SUCCESS"
                    ? "bg-emerald-500/15 text-emerald-300"
                    : status === "ERROR"
                      ? "bg-red-500/15 text-red-300"
                      : "bg-slate-700 text-slate-300"
              }`}
            >
              ● {status}
            </span>
          </div>
        </header>

        <section className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
          <div className="grid gap-4 lg:grid-cols-[1fr_260px_auto]">
            <div>
              <label className="mb-2 block text-xs font-medium uppercase tracking-wide text-slate-400">
                Prompt
              </label>
              <textarea
                value={prompt}
                onChange={(event) => setPrompt(event.target.value)}
                rows={3}
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-sm outline-none focus:border-cyan-500"
              />
            </div>

            <div>
              <label className="mb-2 block text-xs font-medium uppercase tracking-wide text-slate-400">
                Application
              </label>
              <input
                value={applicationName}
                onChange={(event) => setApplicationName(event.target.value)}
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-sm outline-none focus:border-cyan-500"
              />
            </div>

            <div className="flex items-end gap-2">
              <button
                type="button"
                onClick={startInvestigation}
                disabled={
                  status === "RUNNING" ||
                  prompt.trim().length < 3 ||
                  mcpStatus?.mcp !== "healthy"
                }
                className="rounded-xl bg-cyan-500 px-5 py-3 text-sm font-semibold text-slate-950 disabled:cursor-not-allowed disabled:opacity-40"
              >
                Lancer
              </button>
              <button
                type="button"
                onClick={resetRun}
                className="rounded-xl border border-slate-700 px-4 py-3 text-sm text-slate-300"
              >
                Reset
              </button>
            </div>
          </div>

          <div className="mt-4 grid gap-3 text-xs text-slate-400 sm:grid-cols-2 xl:grid-cols-6">
            <div>Start: <span className="text-slate-200">{formatLocalTime(startedAt)}</span></div>
            <div>End: <span className="text-slate-200">{formatLocalTime(finishedAt)}</span></div>
            <div>Run: <span className="font-mono text-slate-200">{runId?.slice(0, 8) ?? "—"}</span></div>
            <div>Trace: <span className="font-mono text-slate-200">{traceId?.slice(0, 8) ?? "—"}</span></div>
            <div>Events: <span className="text-slate-200">{events.length}</span></div>
            <div>MCP: <span className="text-slate-200">{mcpStatus?.protocol_version ?? "—"}</span></div>
          </div>

          {errorMessage && (
            <div className="mt-4 rounded-xl border border-red-900 bg-red-950/40 px-4 py-3 text-sm text-red-300">
              {errorMessage}
            </div>
          )}
        </section>

        <section className="rounded-2xl border border-slate-800 bg-slate-900/70 px-5 py-4">
          <div className="flex flex-wrap gap-x-5 gap-y-2 text-xs">
            {(Object.keys(TYPE_META) as SpanType[])
              .filter((type) => type !== "OTHER" && type !== "TOOL")
              .map((type) => (
                <div key={type} className="flex items-center gap-2 text-slate-300">
                  <span
                    className="h-2.5 w-2.5 rounded-full"
                    style={{ background: TYPE_META[type].dot }}
                  />
                  {TYPE_META[type].label}
                </div>
              ))}
            <div className="flex items-center gap-2 text-slate-300">
              <span className="h-2.5 w-2.5 rounded-full bg-red-500" />
              ERROR
            </div>
          </div>
        </section>

        <section className="grid gap-5 xl:grid-cols-[1.15fr_0.85fr]">
          <div className="overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/70">
            <div className="border-b border-slate-800 px-5 py-4">
              <h2 className="font-semibold">LIVE AGENT GRAPH</h2>
              <p className="text-xs text-slate-400">
                NODE LangGraph → MCP remote call → LLM.
              </p>
            </div>
            <div className="h-[720px]">
              <ReactFlow
                nodes={graphNodes}
                edges={graphEdges}
                fitView
                fitViewOptions={{ padding: 0.18 }}
              >
                <Background />
                <Controls />
                <MiniMap pannable zoomable />
              </ReactFlow>
            </div>
          </div>

          <div className="overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/70">
            <div className="border-b border-slate-800 px-5 py-4">
              <h2 className="font-semibold">EVENT STREAM</h2>
              <p className="text-xs text-slate-400">Flux SSE reçu depuis FastAPI.</p>
            </div>
            <div className="max-h-[720px] overflow-y-auto">
              {events.length === 0 ? (
                <div className="p-5 text-sm text-slate-500">
                  Aucun événement pour le moment.
                </div>
              ) : (
                events.map((event, index) => {
                  const data = event.event_data ?? {};
                  return (
                    <div
                      key={`${event.sequence_no ?? index}-${event.event_type}-${index}`}
                      className="grid grid-cols-[110px_1fr_auto] gap-3 border-b border-slate-800/80 px-4 py-3 text-xs even:bg-slate-950/25"
                    >
                      <div className="font-mono text-slate-500">
                        {event.occurred_at
                          ? new Date(event.occurred_at).toLocaleTimeString("fr-FR", {
                              hour12: false,
                              hour: "2-digit",
                              minute: "2-digit",
                              second: "2-digit",
                              fractionalSecondDigits: 3,
                            })
                          : "—"}
                      </div>
                      <div className="min-w-0">
                        <div className="font-medium text-slate-200">
                          {event.event_type}
                        </div>
                        <div className="truncate text-slate-500">
                          {String(
                            data.name ??
                              data.tool ??
                              data.application ??
                              data.selected ??
                              ""
                          )}
                        </div>
                      </div>
                      <div className="text-right font-mono text-slate-300">
                        {data.duration_ms !== undefined
                          ? `${String(data.duration_ms)} ms`
                          : ""}
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </section>

        <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-8">
          <MetricCard
            label="Total Trace"
            value={breakdown ? formatDuration(breakdown.total_ms) : "—"}
            detail="100 %"
          />
          <MetricCard
            label="MCP Calls"
            value={breakdown ? formatDuration(breakdown.mcp_duration_ms ?? 0) : "—"}
            detail={breakdown ? `${breakdown.mcp_pct ?? 0}%` : "round-trip"}
          />
          <MetricCard
            label="LLM"
            value={breakdown ? formatDuration(breakdown.llm_duration_ms ?? 0) : "—"}
            detail={breakdown ? `${breakdown.llm_pct ?? 0}%` : llmMetric?.model ?? "—"}
          />
          <MetricCard
            label="Unattributed"
            value={breakdown ? formatDuration(breakdown.unattributed_ms) : "—"}
            detail={breakdown ? `${breakdown.unattributed_pct}%` : "—"}
          />
          <MetricCard
            label="Tokens"
            value={llmMetric ? String(llmMetric.total_tokens) : "—"}
            detail={llmMetric ? `${llmMetric.input_tokens} in / ${llmMetric.output_tokens} out` : "—"}
          />
          <MetricCard
            label="Cost"
            value={llmMetric ? `$${llmMetric.estimated_cost_usd.toFixed(6)}` : "—"}
            detail={llmMetric?.model ?? "—"}
          />
          <MetricCard
            label="Errors"
            value={String(spans.filter((span) => span.status === "ERROR").length)}
            detail={`${spans.length} spans`}
          />
          <MetricCard label="Judge Score" value="—" detail="Module 3" />
        </section>

        {breakdown && (
          <section className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
            <div className="mb-4 flex flex-wrap items-end justify-between gap-2">
              <div>
                <h2 className="font-semibold">EXECUTION BREAKDOWN</h2>
                <p className="text-xs text-slate-400">
                  Répartition du temps sur 100 % de la trace.
                </p>
              </div>
              <div className="font-mono text-sm text-slate-300">
                {breakdown.total_ms} ms = 100 %
              </div>
            </div>

            <BreakdownBar
              label="MCP round-trip"
              ms={breakdown.mcp_duration_ms ?? 0}
              pct={breakdown.mcp_pct ?? 0}
            />
            <BreakdownBar
              label="LLM"
              ms={breakdown.llm_duration_ms ?? 0}
              pct={breakdown.llm_pct ?? 0}
            />
            <BreakdownBar
              label="Unattributed"
              ms={breakdown.unattributed_ms}
              pct={breakdown.unattributed_pct}
            />

            {breakdown.note && (
              <p className="mt-4 text-xs text-slate-500">{breakdown.note}</p>
            )}
          </section>
        )}

        {diagnosis && (
          <section className="rounded-2xl border border-emerald-900/60 bg-emerald-950/10 p-5">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <h2 className="font-semibold">LLM DIAGNOSIS</h2>
              <span className="text-xs text-emerald-300">
                {llmMetric?.provider} · {llmMetric?.model}
              </span>
            </div>
            <div className="whitespace-pre-wrap rounded-xl bg-slate-950 p-4 text-sm leading-6 text-slate-200">
              {diagnosis}
            </div>
          </section>
        )}

        {summary && (
          <section className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
            <h2 className="mb-3 font-semibold">INVESTIGATION SUMMARY</h2>
            <pre className="overflow-x-auto rounded-xl bg-slate-950 p-4 text-xs text-slate-300">
              {JSON.stringify(summary, null, 2)}
            </pre>
          </section>
        )}
      </div>
    </main>
  );
}

function MetricCard({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-4">
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-2 text-2xl font-semibold">{value}</div>
      <div className="mt-1 text-xs text-slate-400">{detail}</div>
    </div>
  );
}

function BreakdownBar({
  label,
  ms,
  pct,
}: {
  label: string;
  ms: number;
  pct: number;
}) {
  return (
    <div className="mb-4">
      <div className="mb-2 flex items-center justify-between gap-4 text-sm">
        <span>{label}</span>
        <span className="font-mono text-slate-300">
          {ms} ms · {pct}%
        </span>
      </div>
      <div className="h-3 overflow-hidden rounded-full bg-slate-800">
        <div
          className="h-full rounded-full bg-cyan-500 transition-all duration-500"
          style={{ width: `${Math.max(0, Math.min(100, pct))}%` }}
        />
      </div>
    </div>
  );
}
