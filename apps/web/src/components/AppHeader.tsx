import { ChartLine } from "@phosphor-icons/react";
import { StatusPill, StatusTone } from "@/components/ui/StatusPill";

type RunStatus = "IDLE" | "RUNNING" | "SUCCESS" | "ERROR";

const STATUS_TONE: Record<RunStatus, StatusTone> = {
  IDLE: "idle",
  RUNNING: "running",
  SUCCESS: "success",
  ERROR: "error",
};

const STATUS_LABEL: Record<RunStatus, string> = {
  IDLE: "Idle",
  RUNNING: "Running",
  SUCCESS: "Success",
  ERROR: "Error",
};

export function AppHeader({ status }: { status: RunStatus }) {
  return (
    <header className="flex flex-col gap-4 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-surface)] p-5 shadow-[var(--shadow-sm)] sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-center gap-3">
        <span
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[var(--radius-md)] bg-[var(--color-surface-raised)] text-[var(--color-brand)]"
          aria-hidden="true"
        >
          <ChartLine size={22} weight="bold" />
        </span>
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[var(--color-brand)]">
            GenAI Enterprise Lab
          </div>
          <h1 className="text-xl font-semibold text-[var(--color-text-primary)] sm:text-2xl">
            AI Ops Investigator
          </h1>
          <p className="mt-0.5 text-sm text-[var(--color-text-tertiary)]">
            Live Agent Inspector — LangGraph / Trace / Span / SSE
          </p>
        </div>
      </div>

      <div role="status" aria-live="polite">
        <StatusPill tone={STATUS_TONE[status]} label={STATUS_LABEL[status]} />
      </div>
    </header>
  );
}
