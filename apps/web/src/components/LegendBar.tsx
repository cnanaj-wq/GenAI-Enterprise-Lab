import { Card } from "@/components/ui/Card";
import { SpanType, TYPE_META } from "@/lib/span-types";

export function LegendBar() {
  const visibleTypes = (Object.keys(TYPE_META) as SpanType[]).filter((type) => type !== "OTHER");

  return (
    <Card
      as="section"
      aria-label="Span type legend"
      className="px-5 py-4"
    >
      <ul className="flex flex-wrap gap-x-5 gap-y-2 text-xs">
        {visibleTypes.map((type) => (
          <li key={type} className="flex items-center gap-2 text-[var(--color-text-secondary)]">
            <span
              className="h-2.5 w-2.5 rounded-full"
              style={{ background: TYPE_META[type].dot }}
              aria-hidden="true"
            />
            {TYPE_META[type].label}
          </li>
        ))}
        <li className="flex items-center gap-2 text-[var(--color-text-secondary)]">
          <span
            className="h-2.5 w-2.5 rounded-full bg-[var(--color-danger)]"
            aria-hidden="true"
          />
          ERROR
        </li>
      </ul>
    </Card>
  );
}
