import {
  Clock,
  Coins,
  Database,
  Gauge,
  Scales,
  WarningCircle,
  Wrench,
} from "@phosphor-icons/react";
import { MetricCard } from "@/components/ui/MetricCard";
import { Breakdown, LLMMetric } from "@/lib/investigation-types";
import { formatDuration } from "@/lib/span-types";

export function MetricsGrid({
  breakdown,
  llmMetric,
  pureToolMs,
  errorCount,
  spanCount,
}: {
  breakdown: Breakdown | null;
  llmMetric: LLMMetric | null;
  pureToolMs: number;
  errorCount: number;
  spanCount: number;
}) {
  return (
    <section aria-label="Run metrics" className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-8">
      <MetricCard
        icon={<Clock size={14} weight="bold" />}
        label="Total Trace"
        value={breakdown ? formatDuration(breakdown.total_ms) : "—"}
        detail="100 %"
      />
      <MetricCard
        icon={<Wrench size={14} weight="bold" />}
        label="Pure Tools"
        value={breakdown ? formatDuration(breakdown.tool_execution_ms) : formatDuration(pureToolMs)}
        detail={breakdown ? `${breakdown.tool_execution_pct}%` : "—"}
      />
      <MetricCard
        icon={<Gauge size={14} weight="bold" />}
        label="LLM"
        value={breakdown ? formatDuration(breakdown.llm_duration_ms ?? 0) : "—"}
        detail={breakdown ? `${breakdown.llm_pct ?? 0}%` : llmMetric?.model ?? "—"}
      />
      <MetricCard
        icon={<Database size={14} weight="bold" />}
        label="Unattributed"
        value={breakdown ? formatDuration(breakdown.unattributed_ms) : "—"}
        detail={breakdown ? `${breakdown.unattributed_pct}%` : "—"}
      />
      <MetricCard
        icon={<Coins size={14} weight="bold" />}
        label="Tokens"
        value={llmMetric ? String(llmMetric.total_tokens) : "—"}
        detail={llmMetric ? `${llmMetric.input_tokens} in / ${llmMetric.output_tokens} out` : "—"}
      />
      <MetricCard
        icon={<Coins size={14} weight="bold" />}
        label="Cost"
        value={llmMetric ? `$${llmMetric.estimated_cost_usd.toFixed(6)}` : "—"}
        detail={llmMetric?.model ?? "—"}
      />
      <MetricCard
        icon={<WarningCircle size={14} weight="bold" />}
        label="Errors"
        value={String(errorCount)}
        detail={`${spanCount} spans`}
        tone="danger"
      />
      <MetricCard
        icon={<Scales size={14} weight="bold" />}
        label="Judge Score"
        value="—"
        detail="Module 3"
      />
    </section>
  );
}
