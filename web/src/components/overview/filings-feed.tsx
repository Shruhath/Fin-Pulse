"use client";

import Link from "next/link";
import clsx from "clsx";

import { SentimentIcon } from "@/components/ui/sentiment";
import { SourceBadge } from "@/components/ui/source-badge";
import type { FilingItem } from "@/lib/api/types";
import { fmtDay, fmtTime } from "@/lib/format";
import { useFocus } from "./focus";

const STATUS: Record<FilingItem["status"], string | null> = {
  analysed: null,
  parsed: "Awaiting analysis",
  ingested: "Queued for parsing",
  failed: "Failed to parse",
};

export function FilingsFeed({ filings }: { filings: FilingItem[] }) {
  const { entityId, day, setFocus } = useFocus();

  return (
    <ol className="divide-y divide-line">
      {filings.map((f) => {
        const linked =
          (entityId && f.entities.some((e) => e.id === entityId)) || (day && f.publishedAt.slice(0, 10) === day);
        const dim = (entityId || day) && !linked;
        return (
          <li
            key={f.id}
            onPointerEnter={() => setFocus({ entityId: f.entities[0]?.id ?? null, day: f.publishedAt.slice(0, 10) })}
            onPointerLeave={() => setFocus({ entityId: null, day: null })}
            className={clsx(
              "relative px-4 py-3 transition-[background-color,opacity] duration-150",
              linked && "bg-accent-weak/60",
              dim && "opacity-55",
            )}
          >
            <div className="flex items-center gap-2 text-xs text-ink-3">
              <SourceBadge kind={f.source} />
              <time dateTime={f.publishedAt} className="num">
                {fmtDay(f.publishedAt)} · {fmtTime(f.publishedAt)}
              </time>
              {STATUS[f.status] && <span className="ml-auto text-2xs font-medium text-warn">{STATUS[f.status]}</span>}
            </div>
            <Link
              href={`/filings/${f.id}`}
              className="mt-1.5 block text-sm font-medium text-ink no-underline after:absolute after:inset-0 hover:text-accent-ink"
            >
              {f.title}
            </Link>
            {f.entities.length > 0 && (
              <ul className="mt-2 flex flex-wrap gap-x-3 gap-y-1">
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
