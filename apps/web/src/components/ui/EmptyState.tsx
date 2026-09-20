import { ReactNode } from "react";

export function EmptyState({ icon, title, description }: { icon: ReactNode; title: string; description?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-5 py-12 text-center">
      <span className="text-[var(--color-text-disabled)]" aria-hidden="true">
        {icon}
      </span>
      <p className="text-sm font-medium text-[var(--color-text-secondary)]">{title}</p>
      {description && (
        <p className="max-w-xs text-xs text-[var(--color-text-tertiary)]">{description}</p>
      )}
    </div>
  );
}
