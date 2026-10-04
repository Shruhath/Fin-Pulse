"use client";

import Link from "next/link";
import clsx from "clsx";

import { useFocus } from "@/components/linked/focus";
import { SentimentPill } from "@/components/ui/sentiment";
import { Empty } from "@/components/ui/states";
import type { DocumentDetail, SentimentLabel } from "@/lib/api/types";
import { fmtPct } from "@/lib/format";
import { EventCard } from "./event-card";

/** Who the filing is about, how it reads for each of them, and what happened. */
export function EntityInspector({ doc }: { doc: DocumentDetail }) {
  const { entityId, setFocus } = useFocus();
  const byEntity = new Map<string, { surface: string; n: number; conf: number; votes: Record<SentimentLabel, number> }>();
  for (const s of doc.spans) {
    const e = byEntity.get(s.entityId) ?? { surface: s.surface, n: 0, conf: 0, votes: { positive: 0, negative: 0, neutral: 0 } };
    e.n += 1;
    e.conf += s.confidence;
    e.votes[s.sentiment] += 1;
    if (s.surface.length > e.surface.length) e.surface = s.surface;
    byEntity.set(s.entityId, e);
  }
  const names = new Map(doc.entities.map((e) => [e.id, e.name]));

  return (
    <div className="divide-y divide-line">
      <section className="p-3">
        <h3 className="font-mono text-2xs text-ink-3">entities resolved</h3>
        {byEntity.size === 0 ? (
          <Empty>No company mentions resolved in this filing yet.</Empty>
        ) : (
          <ul className="mt-2 space-y-1">
            {[...byEntity].map(([id, e]) => {
              const label = (Object.entries(e.votes).sort((a, b) => b[1] - a[1])[0][0]) as SentimentLabel;
              return (
                <li
                  key={id}
                  onPointerEnter={() => setFocus({ entityId: id })}
                  onPointerLeave={() => setFocus({ entityId: null })}
                  className={clsx("flex items-center gap-2 px-2 py-1.5", entityId === id ? "bg-surface-2" : "")}
                >
                  <div className="min-w-0 flex-1">
                    <Link href={`/companies/${id}`} className="block truncate text-sm font-medium text-ink no-underline hover:text-accent-ink">
                      {names.get(id) ?? e.surface}
                    </Link>
                    <p className="font-mono text-2xs text-ink-3">
                      {e.n} mention{e.n > 1 ? "s" : ""} · conf {fmtPct(e.conf / e.n)}
                    </p>
                  </div>
                  <SentimentPill sentiment={label} />
                </li>
              );
            })}
          </ul>
        )}
      </section>
      <section className="p-3">
        <h3 className="font-mono text-2xs text-ink-3">events extracted</h3>
        {doc.events.length === 0 ? (
          <Empty>{doc.status === "analysed" ? "No event matched the taxonomy." : "Event extraction has not run yet."}</Empty>
        ) : (
          <div className="mt-3 space-y-6">
            {doc.events.map((e) => (
              <EventCard key={e.id} event={e} showSourceLink={false} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
