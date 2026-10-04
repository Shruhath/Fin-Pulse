"use client";

import { useMemo, useState } from "react";
import clsx from "clsx";

import { EventTimeline, GROUPS } from "@/components/charts/event-timeline";
import { useFocus } from "@/components/linked/focus";
import { EventCard } from "@/components/tiles/event-card";
import { SentimentIcon } from "@/components/ui/sentiment";
import { SourceBadge } from "@/components/ui/source-badge";
import { Empty } from "@/components/ui/states";
import { Workspace } from "@/components/wm/workspace";
import type { EventGroup, EventRecord } from "@/lib/api/types";
import { fmtDay } from "@/lib/format";

export function EventsWorkspace({ events, windowDays, windowLabel }: { events: EventRecord[]; windowDays: number; windowLabel: string }) {
  const [group, setGroup] = useState<EventGroup | "all">("all");
  const [selectedId, setSelectedId] = useState<string | null>(events[0]?.id ?? null);
  const shown = useMemo(() => (group === "all" ? events : events.filter((e) => e.group === group)), [events, group]);
  const selected = events.find((e) => e.id === selectedId) ?? null;

  return (
    <Workspace
      tiles={[
        {
          id: "timeline",
          cls: "chart",
          title: `event timeline · ${windowLabel}`,
          flush: true,
          mobileMinH: 300,
          meta: <ShapeLegend />,
          node: events.length ? (
            <div className="h-full px-1 pt-2">
              <EventTimeline events={shown} selectedId={selectedId} onSelect={setSelectedId} windowDays={windowDays} />
            </div>
          ) : (
            <Empty>No events extracted in this window.</Empty>
          ),
        },
        {
          id: "event-log",
          cls: "log",
          title: "events",
          weight: 1.5,
          flush: true,
          meta: <span className="font-mono">{shown.length}</span>,
          node: <EventLog events={shown} group={group} onGroup={setGroup} selectedId={selectedId} onSelect={setSelectedId} />,
        },
        {
          id: "event-inspect",
          cls: "inspect",
          title: selected ? `${selected.type.toLowerCase()} · ${selected.entityName.toLowerCase()}` : "event",
          weight: 1.3,
          node: selected ? <EventCard event={selected} /> : <Empty>Select an event on the timeline or in the log.</Empty>,
        },
      ]}
    />
  );
}

function ShapeLegend() {
  const item = (d: string, fill: string, label: string) => (
    <span className="flex items-center gap-1">
      <svg viewBox="0 0 10 10" className="size-2.5" aria-hidden="true">
        <path d={d} fill={fill} />
      </svg>
      {label}
    </span>
  );
  return (
    <span className="hidden items-center gap-3 font-mono sm:flex">
      {item("M5 1 9.5 9h-9Z", "var(--pos)", "positive")}
      {item("M5 9 .5 1h9Z", "var(--neg)", "negative")}
      {item("M5 1.5a3.5 3.5 0 1 1 0 7 3.5 3.5 0 0 1 0-7Z", "var(--neu)", "neutral")}
    </span>
  );
}

function EventLog({
  events,
  group,
  onGroup,
  selectedId,
  onSelect,
}: {
  events: EventRecord[];
  group: EventGroup | "all";
  onGroup: (g: EventGroup | "all") => void;
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const { entityId, setFocus } = useFocus();
  return (
    <div>
      <div role="group" aria-label="Filter by event group" className="sticky top-0 z-[1] flex flex-wrap gap-1 border-b border-line bg-surface p-2">
        {(["all", ...GROUPS] as const).map((g) => (
          <button
            key={g}
            type="button"
            aria-pressed={group === g}
            onClick={() => onGroup(g)}
            className={clsx(
              "border px-2 py-0.5 font-mono text-2xs transition-colors",
              group === g ? "border-ring bg-accent-weak text-accent-ink" : "border-line text-ink-3 hover:text-ink",
            )}
          >
            {g.toLowerCase()}
          </button>
        ))}
      </div>
      {events.length === 0 ? (
        <Empty>No events in this group.</Empty>
      ) : (
        <ol className="divide-y divide-line">
          {events.map((e) => (
            <li key={e.id}>
              <button
                type="button"
                onClick={() => onSelect(e.id)}
                onPointerEnter={() => setFocus({ entityId: e.entityId })}
                onPointerLeave={() => setFocus({ entityId: null })}
                aria-pressed={selectedId === e.id}
                className={clsx(
                  "grid w-full grid-cols-[16px_1fr] gap-x-2 px-3 py-2 text-left transition-colors",
                  selectedId === e.id ? "bg-accent-weak outline outline-1 -outline-offset-1 outline-ring" : entityId === e.entityId ? "bg-surface-2" : "hover:bg-surface-2",
                )}
              >
                <SentimentIcon sentiment={e.sentiment} className="mt-0.5 size-3.5" />
                <span className="min-w-0">
                  <span className="flex items-center gap-2 font-mono text-2xs text-ink-3">
                    <SourceBadge kind={e.source} />
                    {fmtDay(e.t)}
                    <span className="truncate text-accent-ink">{e.type}</span>
                  </span>
                  <span className="mt-0.5 block text-sm font-medium text-ink">{e.entityName}</span>
                  <span className="block truncate text-xs text-ink-2">{e.headline}</span>
                </span>
              </button>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
