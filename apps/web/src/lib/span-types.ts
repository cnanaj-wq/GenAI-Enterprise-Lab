export type SpanStatus = "RUNNING" | "SUCCESS" | "ERROR" | "WAITING";
export type SpanType = "NODE" | "TOOL" | "DATABASE" | "LLM" | "EVALUATION" | "OTHER";

export type SpanView = {
  spanId: string;
  parentSpanId?: string | null;
  name: string;
  spanType: SpanType;
  status: SpanStatus;
  durationMs?: number;
  pureToolMs?: number;
  sequenceNo: number;
};

export const TYPE_META: Record<
  SpanType,
  { label: string; border: string; bg: string; dot: string }
> = {
  NODE: {
    label: "NODE LangGraph",
    border: "var(--color-type-node)",
    bg: "var(--color-type-node-bg)",
    dot: "var(--color-type-node)",
  },
  TOOL: {
    label: "TOOL",
    border: "var(--color-type-tool)",
    bg: "var(--color-type-tool-bg)",
    dot: "var(--color-type-tool)",
  },
  DATABASE: {
    label: "DATABASE",
    border: "var(--color-type-database)",
    bg: "var(--color-type-database-bg)",
    dot: "var(--color-type-database)",
  },
  LLM: {
    label: "LLM",
    border: "var(--color-type-llm)",
    bg: "var(--color-type-llm-bg)",
    dot: "var(--color-type-llm)",
  },
  EVALUATION: {
    label: "EVALUATION",
    border: "var(--color-type-evaluation)",
    bg: "var(--color-type-evaluation-bg)",
    dot: "var(--color-type-evaluation)",
  },
  OTHER: {
    label: "OTHER",
    border: "var(--color-type-other)",
    bg: "var(--color-type-other-bg)",
    dot: "var(--color-type-other)",
  },
};

export function normalizeSpanType(value: unknown): SpanType {
  const normalized = String(value ?? "OTHER").toUpperCase();
  if (
    normalized === "NODE" ||
    normalized === "TOOL" ||
    normalized === "DATABASE" ||
    normalized === "LLM" ||
    normalized === "EVALUATION"
  ) {
    return normalized;
  }
  return "OTHER";
}

export function formatLocalTime(iso?: string | null) {
  if (!iso) return "—";
  return new Intl.DateTimeFormat("fr-FR", {
    dateStyle: "short",
    timeStyle: "medium",
  }).format(new Date(iso));
}

export function formatDuration(ms?: number) {
  if (ms === undefined || ms === null) return "—";
  if (ms < 1000) return `${ms} ms`;
  return `${(ms / 1000).toFixed(2)} s`;
}

export function statusSymbol(status: SpanStatus) {
  if (status === "SUCCESS") return "✓";
  if (status === "ERROR") return "✕";
  if (status === "RUNNING") return "●";
  return "○";
}
