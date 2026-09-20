import { ArrowsClockwise, Play, WarningCircle } from "@phosphor-icons/react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { TextAreaField, TextField } from "@/components/ui/Field";
import { formatLocalTime } from "@/lib/span-types";

type RunStatus = "IDLE" | "RUNNING" | "SUCCESS" | "ERROR";

export function InvestigationForm({
  prompt,
  onPromptChange,
  applicationName,
  onApplicationNameChange,
  status,
  onStart,
  onReset,
  startedAt,
  finishedAt,
  runId,
  traceId,
  eventCount,
  errorMessage,
}: {
  prompt: string;
  onPromptChange: (value: string) => void;
  applicationName: string;
  onApplicationNameChange: (value: string) => void;
  status: RunStatus;
  onStart: () => void;
  onReset: () => void;
  startedAt: string | null;
  finishedAt: string | null;
  runId: string | null;
  traceId: string | null;
  eventCount: number;
  errorMessage: string | null;
}) {
  const isRunning = status === "RUNNING";

  return (
    <Card className="p-5">
      <div className="grid gap-4 lg:grid-cols-[1fr_260px_auto]">
        <TextAreaField
          label="Prompt"
          value={prompt}
          onChange={(event) => onPromptChange(event.target.value)}
          rows={3}
        />

        <TextField
          label="Application"
          value={applicationName}
          onChange={(event) => onApplicationNameChange(event.target.value)}
        />

        <div className="flex items-end gap-2">
          <Button
            type="button"
            onClick={onStart}
            loading={isRunning}
            disabled={isRunning || prompt.trim().length < 3}
          >
            {!isRunning && <Play size={16} weight="fill" aria-hidden="true" />}
            {isRunning ? "Running" : "Launch"}
          </Button>
          <Button type="button" variant="secondary" onClick={onReset}>
            <ArrowsClockwise size={16} weight="bold" aria-hidden="true" />
            Reset
          </Button>
        </div>
      </div>

      <dl className="mt-5 grid gap-3 text-xs text-[var(--color-text-tertiary)] sm:grid-cols-2 xl:grid-cols-5">
        <div>
          <dt className="inline">Start: </dt>
          <dd className="inline font-mono text-[var(--color-text-secondary)]">
            {formatLocalTime(startedAt)}
          </dd>
        </div>
        <div>
          <dt className="inline">End: </dt>
          <dd className="inline font-mono text-[var(--color-text-secondary)]">
            {formatLocalTime(finishedAt)}
          </dd>
        </div>
        <div>
          <dt className="inline">Run: </dt>
          <dd className="inline font-mono text-[var(--color-text-secondary)]">
            {runId?.slice(0, 8) ?? "—"}
          </dd>
        </div>
        <div>
          <dt className="inline">Trace: </dt>
          <dd className="inline font-mono text-[var(--color-text-secondary)]">
            {traceId?.slice(0, 8) ?? "—"}
          </dd>
        </div>
        <div>
          <dt className="inline">Events: </dt>
          <dd className="inline font-mono text-[var(--color-text-secondary)]">{eventCount}</dd>
        </div>
      </dl>

      {errorMessage && (
        <div
          role="alert"
          className="mt-4 flex items-start gap-2 rounded-[var(--radius-sm)] border border-[var(--color-danger)]/40 bg-[var(--color-danger-bg)] px-4 py-3 text-sm text-[var(--color-danger)]"
        >
          <WarningCircle size={18} weight="fill" className="mt-0.5 shrink-0" aria-hidden="true" />
          <span>{errorMessage}</span>
        </div>
      )}
    </Card>
  );
}
