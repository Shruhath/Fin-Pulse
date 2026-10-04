"use client";

import Link from "next/link";
import clsx from "clsx";

import { useFocus } from "@/components/linked/focus";
import { SentimentIcon } from "@/components/ui/sentiment";
import { SourceBadge } from "@/components/ui/source-badge";
import type { FilingItem } from "@/lib/api/types";
import { fmtDay, fmtTime } from "@/lib/format";

const STATUS: Record<FilingItem["status"], string | null> = {
  analysed: null,
  parsed: "awaiting analysis",
  ingested: "queued for parsing",
  failed: "parse failed",
};

export function FilingsFeed({ filings, selectedId }: { filings: FilingItem[]; selectedId?: string }) {
  const { entityId, day, setFocus } = useFocus();

  return (
    <ol className="divide-y divide-line">
      {filings.map((f) => {
        const linked = (entityId && f.entities.some((e) => e.id === entityId)) || (day && f.publishedAt.slice(0, 10) === day);
        const dim = (entityId || day) && !linked && f.id !== selectedId;
        const selected = f.id === selectedId;
        return (
          <li
            key={f.id}
            onPointerEnter={() => setFocus({ entityId: f.entities[0]?.id ?? null, day: f.publishedAt.slice(0, 10) })}
            onPointerLeave={() => setFocus({ entityId: null, day: null })}
            className={clsx(
              "relative px-3 py-2.5 transition-[background-color,opacity] duration-150",
              selected ? "bg-accent-weak outline outline-1 -outline-offset-1 outline-ring" : linked ? "bg-surface-2" : "hover:bg-surface-2",
              dim && "opacity-50",
            )}
          >
            <div className="flex items-center gap-2 font-mono text-2xs text-ink-3">
              <SourceBadge kind={f.source} />
              <time dateTime={f.publishedAt}>
                {fmtDay(f.publishedAt)} {fmtTime(f.publishedAt).toLowerCase()}
              </time>
              {STATUS[f.status] && <span className="ml-auto text-warn">{STATUS[f.status]}</span>}
            </div>
            <Link
              href={`/filings/${f.id}`}
              scroll={false}
              aria-current={selected ? "true" : undefined}
              className="mt-1 block text-sm leading-snug font-medium text-ink no-underline after:absolute after:inset-0 hover:text-accent-ink"
            >
              {f.title}
            </Link>
            {f.entities.length > 0 && (
              <ul className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1">
                {f.entities.map((e) => (
                  <li key={e.id} className="flex items-center gap-1 text-xs text-ink-2">
                    <SentimentIcon sentiment={e.sentiment} />
                    {e.name}
                  </li>
                ))}
              </ul>
            )}
          </li>
        );
      })}
    </ol>
  );
}
