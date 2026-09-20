import { Brain } from "@phosphor-icons/react";
import { Card, CardHeader } from "@/components/ui/Card";
import { LLMMetric } from "@/lib/investigation-types";

export function DiagnosisPanel({
  diagnosis,
  llmMetric,
}: {
  diagnosis: string;
  llmMetric: LLMMetric | null;
}) {
  return (
    <Card
      as="section"
      aria-label="LLM diagnosis"
      className="!border-[var(--color-success)]/30 bg-[var(--color-success-bg)]"
    >
      <CardHeader
        title="LLM Diagnosis"
        icon={<Brain size={18} weight="bold" className="text-[var(--color-success)]" />}
        action={
          llmMetric && (
            <span className="text-xs text-[var(--color-success)]">
              {llmMetric.provider} · {llmMetric.model}
            </span>
          )
        }
      />
      <div className="p-5">
        <div className="whitespace-pre-wrap rounded-[var(--radius-md)] bg-[var(--color-canvas)] p-4 text-sm leading-relaxed text-[var(--color-text-primary)]">
          {diagnosis}
        </div>
      </div>
    </Card>
  );
}
