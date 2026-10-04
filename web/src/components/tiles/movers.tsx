"use client";

import Link from "next/link";
import clsx from "clsx";

import { useFocus } from "@/components/linked/focus";
import { SentimentIcon } from "@/components/ui/sentiment";
import type { EntityRow } from "@/lib/api/types";
import { fmtScore } from "@/lib/format";

/** Largest moves over the window, drawn as signed bars on a fixed ±0.5 scale. */
export function Movers({ entities }: { entities: EntityRow[] }) {
  const { entityId, setFocus } = useFocus();
  const top = [...entities].sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta)).slice(0, 8);
  return (
    <ol className="py-1">
      {top.map((e) => {
        const w = Math.min(Math.abs(e.delta) / 0.5, 1) * 50;
        return (
          <li
            key={e.id}
            onPointerEnter={() => setFocus({ entityId: e.id })}
            onPointerLeave={() => setFocus({ entityId: null })}
            className={clsx("grid grid-cols-[minmax(0,1fr)_96px_52px] items-center gap-3 px-3 py-1.5", entityId === e.id && "bg-surface-2")}
          >
            <Link href={`/companies/${e.id}`} className="flex min-w-0 items-center gap-1.5 text-sm text-ink no-underline hover:text-accent-ink">
              <SentimentIcon sentiment={e.sentiment} />
              <span className="truncate">{e.name}</span>
            </Link>
            <span className="relative h-2.5 bg-surface-2" aria-hidden="true">
              <span className="absolute inset-y-0 left-1/2 w-px bg-line-strong" />
              <span
                className={clsx("absolute inset-y-0", e.delta >= 0 ? "left-1/2 bg-pos" : "right-1/2 bg-neg")}
                style={{ width: `${w}%` }}
              />
            </span>
            <span className={clsx("text-right font-mono text-xs", e.delta >= 0 ? "text-pos" : "text-neg")}>{fmtScore(e.delta)}</span>
          </li>
        );
      })}
    </ol>
  );
}
