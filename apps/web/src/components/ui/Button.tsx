import { ButtonHTMLAttributes, forwardRef } from "react";
import { ArrowsClockwise } from "@phosphor-icons/react";

type ButtonVariant = "primary" | "secondary" | "ghost";

const VARIANT_CLASSES: Record<ButtonVariant, string> = {
  primary:
    "bg-[var(--color-brand)] text-[var(--color-on-brand)] hover:bg-[var(--color-brand-strong)] disabled:hover:bg-[var(--color-brand)]",
  secondary:
    "border border-[var(--color-border)] bg-[var(--color-surface-raised)] text-[var(--color-text-primary)] hover:bg-[var(--color-surface-hover)] hover:border-[var(--color-text-tertiary)]",
  ghost:
    "text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-text-primary)]",
};

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  loading?: boolean;
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = "primary", loading = false, disabled, className = "", children, ...props }, ref) => {
    return (
      <button
        ref={ref}
        disabled={disabled || loading}
        aria-busy={loading || undefined}
        className={`inline-flex min-h-11 cursor-pointer items-center justify-center gap-2 rounded-[var(--radius-sm)] px-5 py-2.5 text-sm font-semibold transition-colors duration-150 ease-out focus-visible:outline-2 focus-visible:outline-[var(--focus-ring)] focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-40 ${VARIANT_CLASSES[variant]} ${className}`}
        {...props}
      >
        {loading && (
          <ArrowsClockwise size={16} weight="bold" className="animate-spin" aria-hidden="true" />
        )}
        {children}
      </button>
    );
  }
);

Button.displayName = "Button";
