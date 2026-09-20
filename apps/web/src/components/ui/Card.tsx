import { ElementType, HTMLAttributes, ReactNode } from "react";

type CardProps = HTMLAttributes<HTMLElement> & {
  children: ReactNode;
  as?: ElementType;
};

export function Card({ children, className = "", as: Component = "div", ...props }: CardProps) {
  return (
    <Component
      className={`rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-surface)] shadow-[var(--shadow-sm)] ${className}`}
      {...props}
    >
      {children}
    </Component>
  );
}

export function CardHeader({
  title,
  description,
  icon,
  action,
}: {
  title: string;
  description?: string;
  icon?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3 border-b border-[var(--color-border-subtle)] px-5 py-4">
      <div className="flex items-start gap-3">
        {icon && (
          <span className="mt-0.5 text-[var(--color-brand)]" aria-hidden="true">
            {icon}
          </span>
        )}
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--color-text-primary)]">
            {title}
          </h2>
          {description && (
            <p className="mt-1 text-xs text-[var(--color-text-tertiary)]">{description}</p>
          )}
        </div>
      </div>
      {action}
    </div>
  );
}
