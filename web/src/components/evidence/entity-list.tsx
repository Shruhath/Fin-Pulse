"use client";

import Link from "next/link";
import clsx from "clsx";

import { useFocus } from "@/components/linked/focus";
import { SentimentPill } from "@/components/ui/sentiment";
import { Empty } from "@/components/ui/states";
import type { DocumentDetail, SentimentLabel } from "@/lib/api/types";
import { fmtPct } from "@/lib/format";

/** Who the filing is about and how it reads for each of them. Pointing at one lights its mentions in the text. */
export function EntityList({ doc }: { doc: DocumentDetail }) {
  const { entityId, setFocus } = useFocus();
  const byEntity = new Map<string, { surface: string; n: number; scored: number; conf: number; votes: Record<SentimentLabel, number> }>();
  for (const s of doc.spans) {
    if (s.entityId === null) continue;
    const e = byEntity.get(s.entityId) ?? { surface: s.surface, n: 0, scored: 0, conf: 0, votes: { positive: 0, negative: 0, neutral: 0 } };
    e.n += 1;
    if (s.confidence !== null) {
      e.scored += 1;
      e.conf += s.confidence;
    }
    if (s.sentiment !== null) e.votes[s.sentiment] += 1;
    if (s.surface.length > e.surface.length) e.surface = s.surface;
    byEntity.set(s.entityId, e);
  }
  const names = new Map(doc.entities.map((e) => [e.id, e.name]));

  if (byEntity.size === 0) return <Empty>No company mentions were resolved in this filing yet.</Empty>;
  return (
    <ul className="space-y-1">
      {[...byEntity].map(([id, e]) => {
        const [top, votes] = Object.entries(e.votes).sort((a, b) => b[1] - a[1])[0];
        const label = votes === 0 ? null : (top as SentimentLabel);
        return (
          <li
            key={id}
            onPointerEnter={() => setFocus({ entityId: id })}
            onPointerLeave={() => setFocus({ entityId: null })}
            className={clsx("flex items-center gap-3 rounded-xl px-3 py-2.5 transition-colors", entityId === id ? "bg-surface-2" : "")}
          >
            <div className="min-w-0 flex-1">
              <Link href={`/companies/${id}`} className="block truncate text-base font-medium text-ink no-underline hover:text-brand-ink">
                {names.get(id) ?? e.surface}
              </Link>
              <p className="num text-sm text-ink-3">
                {e.n} mention{e.n > 1 ? "s" : ""} · confidence {fmtPct(e.scored ? e.conf / e.scored : null)}
              </p>
            </div>
            <SentimentPill sentiment={label} />
          </li>
        );
      })}
    </ul>
  );
}
