import { ReactNode } from "react";
import {
  CheckCircle,
  Circle,
  Spinner,
  XCircle,
} from "@phosphor-icons/react";

export type StatusTone = "idle" | "running" | "success" | "error" | "warning";

const TONE_STYLES: Record<StatusTone, { text: string; bg: string; icon: ReactNode }> = {
  idle: {
    text: "text-[var(--color-idle)]",
    bg: "bg-[var(--color-idle-bg)]",
    icon: <Circle size={12} weight="fill" aria-hidden="true" />,
  },
  running: {
    text: "text-[var(--color-warning)]",
    bg: "bg-[var(--color-warning-bg)]",
    icon: <Spinner size={12} weight="bold" className="animate-spin" aria-hidden="true" />,
  },
  success: {
    text: "text-[var(--color-success)]",
    bg: "bg-[var(--color-success-bg)]",
    icon: <CheckCircle size={12} weight="fill" aria-hidden="true" />,
  },
  error: {
    text: "text-[var(--color-danger)]",
    bg: "bg-[var(--color-danger-bg)]",
    icon: <XCircle size={12} weight="fill" aria-hidden="true" />,
  },
  warning: {
    text: "text-[var(--color-warning)]",
    bg: "bg-[var(--color-warning-bg)]",
    icon: <Circle size={12} weight="fill" aria-hidden="true" />,
  },
};

export function StatusPill({ tone, label }: { tone: StatusTone; label: string }) {
  const styles = TONE_STYLES[tone];
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-[var(--radius-full)] px-3 py-1 text-xs font-semibold ${styles.text} ${styles.bg}`}
    >
      {styles.icon}
      {label}
    </span>
  );
}
