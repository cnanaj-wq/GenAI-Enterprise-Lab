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
import ProjectHealthPanel from "@/components/ProjectHealthPanel";
import UsageCostPanel from "@/components/UsageCostPanel";
import OptimizePanel from "@/components/OptimizePanel";

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

type ViewMode = "LIVE" | "HISTORY" | "COMPARE" | "PROJECT HEALTH" | "USAGE & COST" | "OPTIMIZE";

type HistoryItem = {
  trace_id: string;
  prompt: string;
  status: string;
  started_at: string;
  finished_at?: string | null;
  duration_ms?: number | null;
  provider?: string | null;
  model?: string | null;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  estimated_cost_usd: number;
  application_name?: string | null;
  resilience: "OK" | "RETRY" | "FALLBACK" | "FAILED";
};

type TraceReplay = {
  replay: boolean;
  trace: {
    trace_id: string;
    prompt: string;
    status: string;
    started_at: string;
    finished_at?: string | null;
    duration_ms?: number | null;
    provider?: string | null;
    model?: string | null;
    input_tokens?: number | null;
    output_tokens?: number | null;
    estimated_cost_usd?: number | null;
    error_type?: string | null;
    error_message?: string | null;
  };
  spans: Array<{
    span_id: string;
    parent_span_id?: string | null;
    sequence_no: number;
    span_type: string;
    name: string;
    status: string;
    duration_ms?: number | null;
  }>;
  events: EventPayload[];
  summary?: Record<string, unknown> | null;
  diagnosis?: Record<string, unknown> | null;
  execution_breakdown?: Breakdown | null;
};

type CompareMetrics = {
  traceId: string;
  date: string;
  application: string;
  status: string;
  resilience: "OK" | "RETRY" | "FALLBACK" | "FAILED";
  configuredModel: string;
  executionMode: "LLM" | "FALLBACK" | "FAILED";
  totalMs: number;
  mcpMs: number;
  llmMs: number;
  unattributedMs: number;
  inputTokens: number;
  outputTokens: number;
  totalTokens: number;
  costUsd: number;
  errorCount: number;
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


function buildCompareMetrics(replay: TraceReplay): CompareMetrics {
  const events = replay.events ?? [];
  const spans = replay.spans ?? [];
  const breakdown = replay.execution_breakdown;

  const hasFallback = events.some(
    (event) => event.event_type === "fallback_used"
  );
  const hasRetry = events.some(
    (event) => event.event_type === "mcp_retry_scheduled"
  );
  const runFailed = replay.trace.status === "ERROR";

  const resilience: CompareMetrics["resilience"] = runFailed
    ? "FAILED"
    : hasFallback
      ? "FALLBACK"
      : hasRetry
        ? "RETRY"
        : "OK";

  const executionMode: CompareMetrics["executionMode"] = runFailed
    ? "FAILED"
    : hasFallback
      ? "FALLBACK"
      : "LLM";

  const sumSpanType = (spanType: string) =>
    spans
      .filter((span) => span.span_type === spanType)
      .reduce((total, span) => total + Number(span.duration_ms ?? 0), 0);

  const inputTokens = Number(replay.trace.input_tokens ?? 0);
  const outputTokens = Number(replay.trace.output_tokens ?? 0);
  const failedSpans = spans.filter((span) => span.status === "ERROR").length;
  const runErrors = events.filter((event) => event.event_type === "run_error").length;

  return {
    traceId: replay.trace.trace_id,
    date: replay.trace.started_at,
    application: String(replay.summary?.application ?? "—"),
    status: replay.trace.status,
    resilience,
    configuredModel: replay.trace.model ?? "—",
    executionMode,
    totalMs: Number(replay.trace.duration_ms ?? 0),
    mcpMs: Number(breakdown?.mcp_duration_ms ?? sumSpanType("MCP")),
    llmMs: Number(breakdown?.llm_duration_ms ?? sumSpanType("LLM")),
    unattributedMs: Number(
      breakdown?.unattributed_ms ??
        Math.max(
          Number(replay.trace.duration_ms ?? 0) -
            sumSpanType("MCP") -
            sumSpanType("LLM"),
          0
        )
    ),
    inputTokens,
    outputTokens,
    totalTokens: inputTokens + outputTokens,
    costUsd: Number(replay.trace.estimated_cost_usd ?? 0),
    errorCount: failedSpans + runErrors,
  };
}

function deltaPercent(a: number, b: number): number | null {
  if (a === 0) return null;
  return ((b - a) / a) * 100;
}

function formatDelta(a: number, b: number): string {
  const delta = deltaPercent(a, b);
  if (delta === null) return a === b ? "0.0%" : "n/a";
  const sign = delta > 0 ? "+" : "";
  return `${sign}${delta.toFixed(1)}%`;
}

function deltaClass(
  a: number,
  b: number,
  mode: "lower-is-better" | "neutral" = "lower-is-better"
) {
  if (a === b) return "text-slate-400";
  if (mode === "neutral") return "text-cyan-300";
  return b < a ? "text-emerald-300" : "text-red-300";
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
  const [degraded, setDegraded] = useState(false);
  const [activeView, setActiveView] = useState<ViewMode>("LIVE");
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [replayMode, setReplayMode] = useState(false);
  const [compareTraceA, setCompareTraceA] = useState("");
  const [compareTraceB, setCompareTraceB] = useState("");
  const [compareA, setCompareA] = useState<TraceReplay | null>(null);
  const [compareB, setCompareB] = useState<TraceReplay | null>(null);
  const [compareLoading, setCompareLoading] = useState(false);
  const [compareError, setCompareError] = useState<string | null>(null);
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
    const timer = window.setTimeout(() => {
      void refreshMcpStatus();
    }, 0);

    return () => window.clearTimeout(timer);
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
    setDegraded(false);
    setReplayMode(false);
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
        const nextSpan: SpanView = {
          spanId,
          parentSpanId,
          name: String(data.name ?? "unknown"),
          spanType: normalizeSpanType(data.span_type),
          status: "RUNNING",
          sequenceNo: Number(data.sequence_no ?? 0),
        };

        return [...without, nextSpan].sort(
          (a, b) => a.sequenceNo - b.sequenceNo
        );
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

    if (event.event_type === "fallback_used") {
      setDegraded(true);
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
      "mcp_retry_scheduled",
      "mcp_circuit_opened",
      "fallback_used",
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

        if (parsed.event_type === "execution_breakdown") {
          source.close();
          sourceRef.current = null;
        }
      });
    }
  }, [applicationName, handleEvent, prompt, refreshMcpStatus, resetRun]);

  const refreshHistory = useCallback(async () => {
    setHistoryLoading(true);
    setHistoryError(null);

    try {
      const response = await fetch(
        `${API_BASE}/api/v1/investigations/history?limit=100`,
        { cache: "no-store" }
      );

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${await response.text()}`);
      }

      const payload = (await response.json()) as {
        count: number;
        items: HistoryItem[];
      };
      setHistory(payload.items);

      if (payload.items.length > 0) {
        setCompareTraceA((current) => current || payload.items[0].trace_id);
      }
      if (payload.items.length > 1) {
        setCompareTraceB((current) => current || payload.items[1].trace_id);
      }
    } catch (error) {
      setHistoryError(error instanceof Error ? error.message : String(error));
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  useEffect(() => {
    if (activeView !== "HISTORY" && activeView !== "COMPARE") {
      return;
    }

    const timer = window.setTimeout(() => {
      void refreshHistory();
    }, 0);

    return () => window.clearTimeout(timer);
  }, [activeView, refreshHistory]);

  const replayHistoricalTrace = useCallback(
    async (historicalTraceId: string) => {
      sourceRef.current?.close();
      sourceRef.current = null;
      setHistoryError(null);

      const response = await fetch(
        `${API_BASE}/api/v1/investigations/traces/${historicalTraceId}/replay`,
        { cache: "no-store" }
      );

      if (!response.ok) {
        setHistoryError(`HTTP ${response.status}: ${await response.text()}`);
        return;
      }

      const replay = (await response.json()) as TraceReplay;
      const replayEvents = replay.events ?? [];
      const replaySpans = replay.spans ?? [];

      setReplayMode(true);
      setActiveView("LIVE");
      setRunId(null);
      setTraceId(replay.trace.trace_id);
      setPrompt(replay.trace.prompt);
      setApplicationName(String(replay.summary?.application ?? ""));
      setStatus(
        replay.trace.status === "SUCCESS"
          ? "SUCCESS"
          : replay.trace.status === "ERROR"
            ? "ERROR"
            : "IDLE"
      );
      setStartedAt(replay.trace.started_at);
      setFinishedAt(replay.trace.finished_at ?? null);
      setEvents(replayEvents);
      setSpans(
        replaySpans.map((span) => ({
          spanId: span.span_id,
          parentSpanId: span.parent_span_id ?? null,
          name: span.name,
          spanType: normalizeSpanType(span.span_type),
          status:
            span.status === "SUCCESS"
              ? "SUCCESS"
              : span.status === "ERROR"
                ? "ERROR"
                : "WAITING",
          durationMs: span.duration_ms ?? undefined,
          sequenceNo: span.sequence_no,
        }))
      );

      setSummary(replay.summary ?? null);
      setBreakdown(replay.execution_breakdown ?? null);

      const diagnosisEvent = [...replayEvents]
        .reverse()
        .find((event) => event.event_type === "diagnosis_ready");

      if (diagnosisEvent?.event_data) {
        setDiagnosis(String(diagnosisEvent.event_data.diagnosis ?? ""));
        setLlmMetric(diagnosisEvent.event_data as unknown as LLMMetric);
      } else {
        setDiagnosis(null);
        setLlmMetric(null);
      }

      setDegraded(
        replayEvents.some((event) => event.event_type === "fallback_used")
      );

      const runError = [...replayEvents]
        .reverse()
        .find((event) => event.event_type === "run_error");

      setErrorMessage(
        runError?.event_data
          ? String(runError.event_data.error_message ?? "Historical run error")
          : null
      );
    },
    []
  );

  const loadComparison = useCallback(async () => {
    setCompareError(null);

    if (!compareTraceA || !compareTraceB) {
      setCompareError("Sélectionne deux traces.");
      return;
    }

    if (compareTraceA === compareTraceB) {
      setCompareError("Trace A et Trace B doivent être différentes.");
      return;
    }

    setCompareLoading(true);

    try {
      const [responseA, responseB] = await Promise.all([
        fetch(
          `${API_BASE}/api/v1/investigations/traces/${compareTraceA}/replay`,
          { cache: "no-store" }
        ),
        fetch(
          `${API_BASE}/api/v1/investigations/traces/${compareTraceB}/replay`,
          { cache: "no-store" }
        ),
      ]);

      if (!responseA.ok) {
        throw new Error(`Trace A: HTTP ${responseA.status}`);
      }
      if (!responseB.ok) {
        throw new Error(`Trace B: HTTP ${responseB.status}`);
      }

      const [payloadA, payloadB] = (await Promise.all([
        responseA.json(),
        responseB.json(),
      ])) as [TraceReplay, TraceReplay];

      setCompareA(payloadA);
      setCompareB(payloadB);
    } catch (error) {
      setCompareError(error instanceof Error ? error.message : String(error));
    } finally {
      setCompareLoading(false);
    }
  }, [compareTraceA, compareTraceB]);

  const compareMetricsA = useMemo(
    () => (compareA ? buildCompareMetrics(compareA) : null),
    [compareA]
  );

  const compareMetricsB = useMemo(
    () => (compareB ? buildCompareMetrics(compareB) : null),
    [compareB]
  );

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

            {degraded && (
              <span className="rounded-full bg-amber-500/15 px-3 py-1 text-xs font-semibold text-amber-300">
                DEGRADED MODE
              </span>
            )}

            {replayMode && (
              <span className="rounded-full bg-violet-500/15 px-3 py-1 text-xs font-semibold text-violet-300">
                REPLAY
              </span>
            )}

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

        <nav className="rounded-2xl border border-slate-800 bg-slate-900/70 p-2">
          <div className="flex flex-wrap gap-2">
            {(["LIVE", "HISTORY", "COMPARE", "PROJECT HEALTH", "USAGE & COST", "OPTIMIZE"] as ViewMode[]).map((view) => (
              <button
                key={view}
                type="button"
                onClick={() => setActiveView(view)}
                className={`rounded-xl px-4 py-2 text-sm font-semibold transition ${
                  activeView === view
                    ? "bg-cyan-500 text-slate-950"
                    : "text-slate-400 hover:bg-slate-800 hover:text-slate-100"
                }`}
              >
                {view}
              </button>
            ))}
          </div>
        </nav>

        {activeView === "HISTORY" ? (
          <section className="overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/70">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 px-5 py-4">
              <div>
                <h2 className="font-semibold">INVESTIGATION HISTORY</h2>
                <p className="text-xs text-slate-400">
                  Traces persistées dans PostgreSQL. Replay = reconstruction sans nouvel appel MCP/LLM.
                </p>
              </div>
              <button
                type="button"
                onClick={() => void refreshHistory()}
                disabled={historyLoading}
                className="rounded-xl border border-slate-700 px-4 py-2 text-sm text-slate-200 disabled:opacity-40"
              >
                {historyLoading ? "Chargement..." : "Rafraîchir"}
              </button>
            </div>

            {historyError && (
              <div className="m-4 rounded-xl border border-red-900 bg-red-950/40 px-4 py-3 text-sm text-red-300">
                {historyError}
              </div>
            )}

            <div className="overflow-x-auto">
              <table className="min-w-full text-left text-xs">
                <thead className="bg-slate-950/70 text-slate-400">
                  <tr>
                    <th className="px-4 py-3">Date</th>
                    <th className="px-4 py-3">Application</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">Resilience</th>
                    <th className="px-4 py-3">Model</th>
                    <th className="px-4 py-3 text-right">Duration</th>
                    <th className="px-4 py-3 text-right">Tokens</th>
                    <th className="px-4 py-3 text-right">Cost</th>
                    <th className="px-4 py-3">Trace</th>
                    <th className="px-4 py-3"></th>
                  </tr>
                </thead>
                <tbody>
                  {history.length === 0 && !historyLoading ? (
                    <tr>
                      <td colSpan={10} className="px-4 py-8 text-center text-slate-500">
                        Aucune trace persistée.
                      </td>
                    </tr>
                  ) : (
                    history.map((item, index) => (
                      <tr
                        key={item.trace_id}
                        className={`border-t border-slate-800 ${
                          index % 2 === 1 ? "bg-slate-950/25" : ""
                        }`}
                      >
                        <td className="whitespace-nowrap px-4 py-3 text-slate-300">
                          {formatLocalTime(item.started_at)}
                        </td>
                        <td className="px-4 py-3 font-medium text-slate-200">
                          {item.application_name ?? "—"}
                        </td>
                        <td className="px-4 py-3">
                          <span
                            className={`rounded-full px-2 py-1 font-semibold ${
                              item.status === "SUCCESS"
                                ? "bg-emerald-500/15 text-emerald-300"
                                : item.status === "ERROR"
                                  ? "bg-red-500/15 text-red-300"
                                  : "bg-amber-500/15 text-amber-300"
                            }`}
                          >
                            {item.status}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-slate-300">{item.resilience}</td>
                        <td className="px-4 py-3 text-slate-300">{item.model ?? "—"}</td>
                        <td className="px-4 py-3 text-right font-mono text-slate-300">
                          {formatDuration(item.duration_ms ?? undefined)}
                        </td>
                        <td className="px-4 py-3 text-right font-mono text-slate-300">
                          {item.total_tokens}
                        </td>
                        <td className="px-4 py-3 text-right font-mono text-slate-300">
                          ${Number(item.estimated_cost_usd ?? 0).toFixed(6)}
                        </td>
                        <td className="px-4 py-3 font-mono text-slate-400">
                          {item.trace_id.slice(0, 8)}
                        </td>
                        <td className="px-4 py-3 text-right">
                          <button
                            type="button"
                            onClick={() => void replayHistoricalTrace(item.trace_id)}
                            className="rounded-lg bg-violet-500/15 px-3 py-2 font-semibold text-violet-300 hover:bg-violet-500/25"
                          >
                            Replay
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </section>
        ) : activeView === "OPTIMIZE" ? (
          <OptimizePanel />
        ) : activeView === "USAGE & COST" ? (
          <UsageCostPanel />
        ) : activeView === "PROJECT HEALTH" ? (
          <ProjectHealthPanel />
        ) : activeView === "COMPARE" ? (
          <section className="space-y-5">
            <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
              <div className="mb-5">
                <h2 className="font-semibold">TRACE COMPARE</h2>
                <p className="mt-1 text-xs text-slate-400">
                  Compare deux exécutions persistées. Delta = Trace B vs Trace A.
                  Aucun appel MCP ou LLM supplémentaire.
                </p>
              </div>

              <div className="grid gap-4 xl:grid-cols-[1fr_1fr_auto]">
                <div>
                  <label className="mb-2 block text-xs font-medium uppercase tracking-wide text-slate-400">
                    Trace A — baseline
                  </label>
                  <select
                    value={compareTraceA}
                    onChange={(event) => setCompareTraceA(event.target.value)}
                    className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-slate-200 outline-none focus:border-cyan-500"
                  >
                    <option value="">Sélectionner...</option>
                    {history.map((item) => (
                      <option key={`A-${item.trace_id}`} value={item.trace_id}>
                        {formatLocalTime(item.started_at)} · {item.application_name ?? "—"} · {item.resilience} · {item.trace_id.slice(0, 8)}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="mb-2 block text-xs font-medium uppercase tracking-wide text-slate-400">
                    Trace B — comparaison
                  </label>
                  <select
                    value={compareTraceB}
                    onChange={(event) => setCompareTraceB(event.target.value)}
                    className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-slate-200 outline-none focus:border-cyan-500"
                  >
                    <option value="">Sélectionner...</option>
                    {history.map((item) => (
                      <option key={`B-${item.trace_id}`} value={item.trace_id}>
                        {formatLocalTime(item.started_at)} · {item.application_name ?? "—"} · {item.resilience} · {item.trace_id.slice(0, 8)}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="flex items-end">
                  <button
                    type="button"
                    onClick={() => void loadComparison()}
                    disabled={compareLoading || !compareTraceA || !compareTraceB}
                    className="w-full rounded-xl bg-cyan-500 px-5 py-3 text-sm font-semibold text-slate-950 disabled:cursor-not-allowed disabled:opacity-40 xl:w-auto"
                  >
                    {compareLoading ? "Comparaison..." : "Comparer"}
                  </button>
                </div>
              </div>

              {compareError && (
                <div className="mt-4 rounded-xl border border-red-900 bg-red-950/40 px-4 py-3 text-sm text-red-300">
                  {compareError}
                </div>
              )}
            </div>

            {compareMetricsA && compareMetricsB ? (
              <div className="overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/70">
                <div className="border-b border-slate-800 px-5 py-4">
                  <h2 className="font-semibold">COMPARISON MATRIX</h2>
                  <p className="mt-1 text-xs text-slate-400">
                    Les couleurs de delta indiquent uniquement l’efficience sur les
                    métriques temps/coût/erreurs. Elles ne mesurent pas la qualité
                    de réponse — celle-ci sera ajoutée avec les évaluations.
                  </p>
                </div>

                <div className="overflow-x-auto">
                  <table className="min-w-full text-left text-sm">
                    <thead className="bg-slate-950/70 text-slate-400">
                      <tr>
                        <th className="px-5 py-4">Metric</th>
                        <th className="px-5 py-4">
                          Trace A
                          <div className="mt-1 font-mono text-xs text-violet-300">
                            {compareMetricsA.traceId.slice(0, 8)}
                          </div>
                        </th>
                        <th className="px-5 py-4">
                          Trace B
                          <div className="mt-1 font-mono text-xs text-cyan-300">
                            {compareMetricsB.traceId.slice(0, 8)}
                          </div>
                        </th>
                        <th className="px-5 py-4 text-right">Delta B vs A</th>
                      </tr>
                    </thead>
                    <tbody>
                      <CompareRow index={0} label="Date" a={formatLocalTime(compareMetricsA.date)} b={formatLocalTime(compareMetricsB.date)} />
                      <CompareRow index={1} label="Application" a={compareMetricsA.application} b={compareMetricsB.application} />
                      <CompareRow index={2} label="Status" a={compareMetricsA.status} b={compareMetricsB.status} />
                      <CompareRow index={3} label="Resilience" a={compareMetricsA.resilience} b={compareMetricsB.resilience} />
                      <CompareRow index={4} label="Configured model" a={compareMetricsA.configuredModel} b={compareMetricsB.configuredModel} />
                      <CompareRow index={5} label="Execution mode" a={compareMetricsA.executionMode} b={compareMetricsB.executionMode} />

                      <CompareNumericRow
                        index={6}
                        label="Total duration"
                        a={compareMetricsA.totalMs}
                        b={compareMetricsB.totalMs}
                        format={formatDuration}
                      />
                      <CompareNumericRow
                        index={7}
                        label="MCP time"
                        a={compareMetricsA.mcpMs}
                        b={compareMetricsB.mcpMs}
                        format={formatDuration}
                      />
                      <CompareNumericRow
                        index={8}
                        label="LLM time"
                        a={compareMetricsA.llmMs}
                        b={compareMetricsB.llmMs}
                        format={formatDuration}
                      />
                      <CompareNumericRow
                        index={9}
                        label="Unattributed"
                        a={compareMetricsA.unattributedMs}
                        b={compareMetricsB.unattributedMs}
                        format={formatDuration}
                      />
                      <CompareNumericRow
                        index={10}
                        label="Input tokens"
                        a={compareMetricsA.inputTokens}
                        b={compareMetricsB.inputTokens}
                        format={(value) => value.toLocaleString("fr-FR")}
                        deltaMode="neutral"
                      />
                      <CompareNumericRow
                        index={11}
                        label="Output tokens"
                        a={compareMetricsA.outputTokens}
                        b={compareMetricsB.outputTokens}
                        format={(value) => value.toLocaleString("fr-FR")}
                        deltaMode="neutral"
                      />
                      <CompareNumericRow
                        index={12}
                        label="Total tokens"
                        a={compareMetricsA.totalTokens}
                        b={compareMetricsB.totalTokens}
                        format={(value) => value.toLocaleString("fr-FR")}
                        deltaMode="neutral"
                      />
                      <CompareNumericRow
                        index={13}
                        label="Estimated cost"
                        a={compareMetricsA.costUsd}
                        b={compareMetricsB.costUsd}
                        format={(value) => `$${value.toFixed(6)}`}
                      />
                      <CompareNumericRow
                        index={14}
                        label="Errors"
                        a={compareMetricsA.errorCount}
                        b={compareMetricsB.errorCount}
                        format={(value) => String(value)}
                      />
                      <CompareRow
                        index={15}
                        label="Trace ID"
                        a={compareMetricsA.traceId}
                        b={compareMetricsB.traceId}
                        mono
                      />
                    </tbody>
                  </table>
                </div>

                <div className="border-t border-slate-800 px-5 py-4 text-xs text-slate-500">
                  Delta = (B − A) / A. « n/a » apparaît lorsque la baseline A vaut zéro.
                  Aucun score qualité n’est déduit de cette comparaison.
                </div>
              </div>
            ) : (
              <div className="rounded-2xl border border-dashed border-slate-700 bg-slate-900/40 px-5 py-12 text-center text-sm text-slate-500">
                Sélectionne deux traces puis clique sur Comparer.
              </div>
            )}
          </section>
        ) : (
          <>

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
                  prompt.trim().length < 3
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
            value={String(
              spans.filter((span) => span.status === "ERROR").length +
                events.filter((event) => event.event_type === "run_error").length
            )}
            detail={`${spans.length} spans`}
          />
          <MetricCard
            label="Resilience"
            value={
              status === "ERROR"
                ? "FAILED"
                : degraded
                  ? "FALLBACK"
                  : events.some((event) => event.event_type === "mcp_retry_scheduled")
                    ? "RETRY"
                    : "OK"
            }
            detail={`${events.filter((event) => event.event_type === "mcp_retry_scheduled").length} retries`}
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
          </>
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

function CompareRow({
  index,
  label,
  a,
  b,
  mono = false,
}: {
  index: number;
  label: string;
  a: string;
  b: string;
  mono?: boolean;
}) {
  return (
    <tr
      className={`border-t border-slate-800 ${
        index % 2 === 1 ? "bg-slate-950/30" : ""
      }`}
    >
      <td className="px-5 py-3 font-medium text-slate-300">{label}</td>
      <td className={`px-5 py-3 text-slate-200 ${mono ? "font-mono text-xs" : ""}`}>
        {a}
      </td>
      <td className={`px-5 py-3 text-slate-200 ${mono ? "font-mono text-xs" : ""}`}>
        {b}
      </td>
      <td className="px-5 py-3 text-right text-slate-600">—</td>
    </tr>
  );
}

function CompareNumericRow({
  index,
  label,
  a,
  b,
  format,
  deltaMode = "lower-is-better",
}: {
  index: number;
  label: string;
  a: number;
  b: number;
  format: (value: number) => string;
  deltaMode?: "lower-is-better" | "neutral";
}) {
  return (
    <tr
      className={`border-t border-slate-800 ${
        index % 2 === 1 ? "bg-slate-950/30" : ""
      }`}
    >
      <td className="px-5 py-3 font-medium text-slate-300">{label}</td>
      <td className="px-5 py-3 font-mono text-slate-200">{format(a)}</td>
      <td className="px-5 py-3 font-mono text-slate-200">{format(b)}</td>
      <td
        className={`px-5 py-3 text-right font-mono font-semibold ${deltaClass(
          a,
          b,
          deltaMode
        )}`}
      >
        {formatDelta(a, b)}
      </td>
    </tr>
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
