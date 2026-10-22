"use client";

import Link from "next/link";
import { ChevronRight } from "lucide-react";
import clsx from "clsx";

import { useFocus } from "@/components/linked/focus";
import { SentimentIcon } from "@/components/ui/sentiment";
import { SourceBadge } from "@/components/ui/source-badge";
import type { FilingItem } from "@/lib/api/types";
import { fmtDay } from "@/lib/format";

const STATUS: Record<FilingItem["status"], string | null> = {
  analysed: null,
  parsed: "Waiting for analysis",
  ingested: "Waiting to be parsed",
  failed: "Could not be parsed",
};

/** A filing as a row: who published it, what it says, which companies it names and how it leans for each. */
export function FilingList({ filings, selectedId, compact = false }: { filings: FilingItem[]; selectedId?: string; compact?: boolean }) {
  const { entityId, setFocus } = useFocus();
  return (
    <ul className="divide-y divide-line overflow-hidden rounded-2xl border border-line bg-surface shadow-1">
      {filings.map((f) => {
        const selected = f.id === selectedId;
        const linked = !!entityId && f.entities.some((e) => e.id === entityId);
        const shown = f.entities.slice(0, compact ? 2 : 3);
        return (
          <li
            key={f.id}
            onPointerEnter={() => f.entities[0] && setFocus({ entityId: f.entities[0].id })}
            onPointerLeave={() => setFocus({ entityId: null })}
            className={clsx(
              "group relative flex items-start gap-3.5 px-4 py-3.5 transition-colors duration-150",
              selected ? "bg-brand-weak" : linked ? "bg-surface-2" : "hover:bg-surface-2",
            )}
          >
            <span className="mt-0.5">
              <SourceBadge kind={f.source} />
            </span>
            <div className="min-w-0 flex-1">
              <Link
                href={`/filings/${f.id}`}
                aria-current={selected ? "true" : undefined}
                className="line-clamp-2 text-base leading-6 font-medium text-ink no-underline after:absolute after:inset-0"
              >
                {f.title}
              </Link>
              <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-ink-3">
                <time dateTime={f.publishedAt ?? undefined}>{fmtDay(f.publishedAt)}</time>
                {STATUS[f.status] && <span className="font-medium text-warn">{STATUS[f.status]}</span>}
                {shown.map((e) => (
                  <span key={e.id} className="inline-flex items-center gap-1 text-ink-2">
                    <SentimentIcon sentiment={e.sentiment} className="size-3.5" />
                    {e.name}
                  </span>
                ))}
                {f.entities.length > shown.length && <span>+{f.entities.length - shown.length} more</span>}
              </p>
            </div>
            <ChevronRight className="mt-1 size-5 shrink-0 text-ink-3 opacity-0 transition-[opacity,transform] duration-200 group-hover:translate-x-0.5 group-hover:opacity-100" aria-hidden="true" />
          </li>
        );
      })}
    </ul>
  );
}
