import { ReactNode } from "react";

export function MetricCard({
  label,
  value,
  detail,
  tone = "neutral",
  icon,
}: {
  label: string;
  value: string;
  detail: string;
  tone?: "neutral" | "danger";
  icon?: ReactNode;
}) {
  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-surface)] p-4 shadow-[var(--shadow-sm)]">
      <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-[var(--color-text-tertiary)]">
        {icon && (
          <span className="text-[var(--color-text-tertiary)]" aria-hidden="true">
            {icon}
          </span>
        )}
        {label}
      </div>
      <div
        className={`mt-2 truncate font-mono text-2xl font-semibold ${
          tone === "danger" && value !== "0"
            ? "text-[var(--color-danger)]"
            : "text-[var(--color-text-primary)]"
        }`}
      >
        {value}
      </div>
      <div className="mt-1 truncate text-xs text-[var(--color-text-secondary)]">{detail}</div>
    </div>
  );
}
