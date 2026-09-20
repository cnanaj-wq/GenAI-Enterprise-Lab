import { ChartBar } from "@phosphor-icons/react";
import { Card, CardHeader } from "@/components/ui/Card";
import { Breakdown } from "@/lib/investigation-types";

function BreakdownBar({ label, ms, pct }: { label: string; ms: number; pct: number }) {
  const clampedPct = Math.max(0, Math.min(100, pct));
  return (
    <div className="mb-4 last:mb-0">
      <div className="mb-2 flex items-center justify-between gap-4 text-sm text-[var(--color-text-primary)]">
        <span>{label}</span>
        <span className="font-mono text-[var(--color-text-secondary)]">
          {ms} ms · {pct}%
        </span>
      </div>
      <div
        role="progressbar"
        aria-label={label}
        aria-valuenow={clampedPct}
        aria-valuemin={0}
        aria-valuemax={100}
        className="h-3 overflow-hidden rounded-[var(--radius-full)] bg-[var(--color-surface-raised)]"
      >
        <div
          className="h-full rounded-[var(--radius-full)] bg-[var(--color-brand)] transition-[width] duration-500 ease-out"
          style={{ width: `${clampedPct}%` }}
        />
      </div>
    </div>
  );
}

export function ExecutionBreakdownPanel({ breakdown }: { breakdown: Breakdown }) {
  return (
    <Card as="section" aria-label="Execution breakdown">
      <CardHeader
        title="Execution Breakdown"
        description="Time distribution across 100% of the trace."
        icon={<ChartBar size={18} weight="bold" />}
        action={
          <span className="font-mono text-sm text-[var(--color-text-secondary)]">
            {breakdown.total_ms} ms = 100%
          </span>
        }
      />

      <div className="p-5">
        <BreakdownBar
          label="Pure Tool execution"
          ms={breakdown.tool_execution_ms}
          pct={breakdown.tool_execution_pct}
        />
        <BreakdownBar label="LLM" ms={breakdown.llm_duration_ms ?? 0} pct={breakdown.llm_pct ?? 0} />
        <BreakdownBar
          label="Unattributed"
          ms={breakdown.unattributed_ms}
          pct={breakdown.unattributed_pct}
        />

        {breakdown.note && (
          <p className="mt-4 text-xs text-[var(--color-text-tertiary)]">{breakdown.note}</p>
        )}
      </div>
    </Card>
  );
}
