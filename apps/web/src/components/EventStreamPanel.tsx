import { Pulse } from "@phosphor-icons/react";
import { Card, CardHeader } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import type { EventPayload } from "@/lib/investigation-types";

export function EventStreamPanel({ events }: { events: EventPayload[] }) {
  return (
    <Card as="section" aria-label="Event stream" className="overflow-hidden">
      <CardHeader
        title="Event Stream"
        description="SSE feed received from FastAPI."
        icon={<Pulse size={18} weight="bold" />}
      />

      <div className="max-h-[420px] overflow-y-auto sm:max-h-[560px] xl:max-h-[720px]" role="log" aria-live="off">
        {events.length === 0 ? (
          <EmptyState
            icon={<Pulse size={28} weight="light" />}
            title="No events yet"
            description="Launch an investigation to start streaming trace events."
          />
        ) : (
          <ul>
            {events.map((event, index) => {
              const data = event.event_data ?? {};
              return (
                <li
                  key={`${event.sequence_no ?? index}-${event.event_type}-${index}`}
                  className="grid grid-cols-[100px_1fr_auto] gap-3 border-b border-[var(--color-border-subtle)] px-4 py-3 text-xs odd:bg-[var(--color-surface-raised)]/40"
                >
                  <div className="font-mono text-[var(--color-text-tertiary)]">
                    {event.occurred_at
                      ? new Date(event.occurred_at).toLocaleTimeString("fr-FR", {
                          hour12: false,
                          hour: "2-digit",
                          minute: "2-digit",
                          second: "2-digit",
                          fractionalSecondDigits: 3,
                        })
                      : "—"}
                  </div>
                  <div className="min-w-0">
                    <div className="font-medium text-[var(--color-text-primary)]">
                      {event.event_type}
                    </div>
                    <div className="truncate text-[var(--color-text-tertiary)]">
                      {String(data.name ?? data.application ?? data.selected ?? "")}
                    </div>
                  </div>
                  <div className="text-right font-mono text-[var(--color-text-secondary)]">
                    {data.duration_ms !== undefined
                      ? `${String(data.duration_ms)} ms`
                      : data.pure_tool_duration_ms !== undefined
                        ? `${String(data.pure_tool_duration_ms)} ms`
                        : ""}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </Card>
  );
}
