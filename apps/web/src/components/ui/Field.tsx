import { InputHTMLAttributes, TextareaHTMLAttributes, useId } from "react";

const fieldControlClasses =
  "w-full rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-[var(--color-canvas)] px-4 py-3 text-sm text-[var(--color-text-primary)] outline-none transition-colors duration-150 placeholder:text-[var(--color-text-disabled)] focus-visible:border-[var(--color-brand)] focus-visible:outline-2 focus-visible:outline-[var(--focus-ring)] focus-visible:outline-offset-2";

function FieldLabel({ htmlFor, children }: { htmlFor: string; children: string }) {
  return (
    <label
      htmlFor={htmlFor}
      className="mb-2 block text-xs font-semibold uppercase tracking-wide text-[var(--color-text-tertiary)]"
    >
      {children}
    </label>
  );
}

type TextFieldProps = InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  helperText?: string;
};

export function TextField({ label, helperText, id, className = "", ...props }: TextFieldProps) {
  const generatedId = useId();
  const fieldId = id ?? generatedId;
  const helperId = helperText ? `${fieldId}-helper` : undefined;

  return (
    <div>
      <FieldLabel htmlFor={fieldId}>{label}</FieldLabel>
      <input
        id={fieldId}
        aria-describedby={helperId}
        className={`${fieldControlClasses} ${className}`}
        {...props}
      />
      {helperText && (
        <p id={helperId} className="mt-1.5 text-xs text-[var(--color-text-tertiary)]">
          {helperText}
        </p>
      )}
    </div>
  );
}

type TextAreaFieldProps = TextareaHTMLAttributes<HTMLTextAreaElement> & {
  label: string;
  helperText?: string;
};

export function TextAreaField({
  label,
  helperText,
  id,
  className = "",
  ...props
}: TextAreaFieldProps) {
  const generatedId = useId();
  const fieldId = id ?? generatedId;
  const helperId = helperText ? `${fieldId}-helper` : undefined;

  return (
    <div>
      <FieldLabel htmlFor={fieldId}>{label}</FieldLabel>
      <textarea
        id={fieldId}
        aria-describedby={helperId}
        className={`${fieldControlClasses} resize-none leading-relaxed ${className}`}
        {...props}
      />
      {helperText && (
        <p id={helperId} className="mt-1.5 text-xs text-[var(--color-text-tertiary)]">
          {helperText}
        </p>
      )}
    </div>
  );
}
