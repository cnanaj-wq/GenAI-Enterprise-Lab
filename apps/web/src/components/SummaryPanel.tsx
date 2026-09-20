import { FileText } from "@phosphor-icons/react";
import { Card, CardHeader } from "@/components/ui/Card";

export function SummaryPanel({ summary }: { summary: Record<string, unknown> }) {
  return (
    <Card as="section" aria-label="Investigation summary">
      <CardHeader title="Investigation Summary" icon={<FileText size={18} weight="bold" />} />
      <div className="p-5">
        <pre className="overflow-x-auto rounded-[var(--radius-md)] bg-[var(--color-canvas)] p-4 font-mono text-xs leading-relaxed text-[var(--color-text-secondary)]">
          {JSON.stringify(summary, null, 2)}
        </pre>
      </div>
    </Card>
  );
}
