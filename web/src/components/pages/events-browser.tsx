"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown } from "lucide-react";
import clsx from "clsx";

import { Segmented } from "@/components/app/segmented";
import { EventTimeline, GROUPS } from "@/components/charts/event-timeline";
import { useFocus } from "@/components/linked/focus";
import { EventCard } from "@/components/evidence/event-card";
import { SentimentIcon } from "@/components/ui/sentiment";
import { SourceBadge } from "@/components/ui/source-badge";
import { Empty } from "@/components/ui/states";
import type { EventGroup, EventRecord } from "@/lib/api/types";
import { fmtDay } from "@/lib/format";

const MONTH = new Intl.DateTimeFormat("en-IN", { month: "long", year: "numeric", timeZone: "Asia/Kolkata" });

/** Events that say the same thing about the same party on the same day, shown once with a count. */
interface Run {
  key: string;
  events: EventRecord[];
}

function ShapeLegend() {
  const item = (d: string, fill: string, label: string) => (
    <span className="flex items-center gap-1.5">
      <svg viewBox="0 0 10 10" className="size-3" aria-hidden="true">
        <path d={d} fill={fill} />
      </svg>
      {label}
    </span>
  );
  return (
    <p className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-ink-3">
      {item("M5 1 9.5 9h-9Z", "var(--pos)", "Positive")}
      {item("M5 9 .5 1h9Z", "var(--neg)", "Negative")}
      {item("M5 1.5a3.5 3.5 0 1 1 0 7 3.5 3.5 0 0 1 0-7Z", "var(--neu)", "Neutral")}
    </p>
  );
}

const sameness = (e: EventRecord) => [e.type, e.entityId ?? e.entityName ?? "", e.headline, e.t?.slice(0, 10) ?? ""].join("|");

/** Extracted events: filter by kind, see them on a timeline, read them by month. Opening one shows the record. */
export function EventsBrowser({ events, windowDays, windowLabel }: { events: EventRecord[]; windowDays: number; windowLabel: string }) {
  const [group, setGroup] = useState<EventGroup | "all">("all");
  const [openKey, setOpenKey] = useState<string | null>(null);
  const shown = useMemo(() => (group === "all" ? events : events.filter((e) => e.group === group)), [events, group]);

  const months = useMemo(() => {
    const out: { label: string; runs: Run[] }[] = [];
    for (const e of shown) {
      const label = e.t ? MONTH.format(new Date(e.t)) : "Undated";
      let month = out[out.length - 1];
      if (!month || month.label !== label) out.push((month = { label, runs: [] }));
      const key = sameness(e);
      const run = month.runs.find((r) => r.key === key);
      if (run) run.events.push(e);
      else month.runs.push({ key, events: [e] });
    }
    return out;
  }, [shown]);

  const counts = useMemo(() => {
    const c = new Map<string, number>();
    for (const e of events) c.set(e.group, (c.get(e.group) ?? 0) + 1);
    return c;
  }, [events]);

  const fromTimeline = (id: string) => {
    const e = shown.find((x) => x.id === id);
    if (!e) return;
    const key = sameness(e);
    setOpenKey(key);
    requestAnimationFrame(() => document.getElementById(`event-${key}`)?.scrollIntoView({ block: "center", behavior: "smooth" }));
  };
  const selectedId = openKey ? (shown.find((e) => sameness(e) === openKey)?.id ?? null) : null;

  if (events.length === 0) return <Empty>No events were extracted in the {windowLabel}.</Empty>;

  return (
    <div className="space-y-8">
      <div className="max-w-full overflow-x-auto">
        <Segmented
          label="Kind of event"
          value={group}
          onChange={setGroup}
          items={[
            { value: "all" as const, label: "All", count: events.length },
            ...GROUPS.filter((g) => counts.has(g)).map((g) => ({ value: g, label: g, count: counts.get(g) })),
          ]}
        />
      </div>

      <section aria-label="Events over time" className="rounded-2xl border border-line bg-surface p-4 shadow-1">
        <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
          <p className="text-sm text-ink-2">Each mark is an event, placed on its day over the {windowLabel}.</p>
          <ShapeLegend />
        </div>
        <div className="h-[230px]">
          <EventTimeline events={shown} selectedId={selectedId} onSelect={fromTimeline} windowDays={windowDays} />
        </div>
      </section>

      {shown.length === 0 ? (
        <Empty>No events of that kind in this window.</Empty>
      ) : (
        months.map((m) => (
          <section key={m.label}>
            <h2 className="mb-3 text-lg font-semibold text-ink">{m.label}</h2>
            <ul className="divide-y divide-line overflow-hidden rounded-2xl border border-line bg-surface shadow-1">
              {m.runs.map((r) => (
                <EventRow key={r.key} run={r} open={openKey === r.key} onToggle={() => setOpenKey(openKey === r.key ? null : r.key)} />
              ))}
            </ul>
          </section>
        ))
      )}
    </div>
  );
}

function EventRow({ run, open, onToggle }: { run: Run; open: boolean; onToggle: () => void }) {
  const { setFocus } = useFocus();
  const panel = useRef<HTMLDivElement>(null);
  const e = run.events[0];
  const n = run.events.length;
  useEffect(() => {
    if (panel.current) panel.current.inert = !open;
  }, [open]);
  return (
    <li id={`event-${run.key}`} className={clsx("transition-colors", open && "bg-surface-2/60")}>
      <button
        type="button"
        onClick={onToggle}
        onPointerEnter={() => setFocus({ entityId: e.entityId })}
        onPointerLeave={() => setFocus({ entityId: null })}
        aria-expanded={open}
        className="flex w-full items-start gap-3.5 px-4 py-3.5 text-left transition-colors hover:bg-surface-2"
      >
        <SentimentIcon sentiment={e.sentiment} className="mt-1 size-4" />
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-ink-3">
            <SourceBadge kind={e.source} />
            <span className="font-semibold text-brand-ink">{e.type}</span>
            <time dateTime={e.t ?? undefined}>{fmtDay(e.t)}</time>
            {n > 1 && <span className="num rounded-full bg-surface-3 px-2 py-0.5 text-xs font-semibold text-ink-2">{n} filings</span>}
          </span>
          <span className={clsx("mt-1 block text-base font-medium", e.entityName ? "text-ink" : "text-ink-2")}>{e.entityName ?? "Unresolved party"}</span>
          <span className={clsx("block text-sm text-ink-2", !open && "line-clamp-1")}>{e.headline}</span>
        </span>
        <ChevronDown className={clsx("mt-1 size-5 shrink-0 text-ink-3 transition-transform duration-200", open && "rotate-180")} aria-hidden="true" />
      </button>
      <div className={clsx("grid transition-[grid-template-rows] duration-300 ease-(--ease-out)", open ? "grid-rows-[1fr]" : "grid-rows-[0fr]")}>
        <div ref={panel} className="overflow-hidden">
          <div className="space-y-6 px-4 pt-1 pb-5 sm:pl-[3.4rem]">
            {run.events.map((ev) => (
              <div key={ev.id} className={n > 1 ? "border-b border-line pb-6 last:border-0 last:pb-0" : undefined}>
                <EventCard event={ev} />
              </div>
            ))}
          </div>
        </div>
      </div>
    </li>
  );
}
