"use client";

import Link from "next/link";
import clsx from "clsx";

import { useFocus } from "@/components/linked/focus";
import { Delta } from "@/components/ui/sentiment";
import type { EntityRow } from "@/lib/api/types";
import { magnitude } from "@/lib/format";

/** The companies whose reading moved most over the window, as signed bars on a fixed ±0.5 scale. */
export function Movers({ entities, limit = 6 }: { entities: EntityRow[]; limit?: number }) {
  const { entityId, setFocus } = useFocus();
  const top = [...entities].sort((a, b) => magnitude(b.delta) - magnitude(a.delta)).slice(0, limit);
  return (
    <ol className="divide-y divide-line overflow-hidden rounded-2xl border border-line bg-surface shadow-1">
      {top.map((e) => {
        const delta = e.delta ?? 0;
        const w = Math.min(Math.abs(delta) / 0.5, 1) * 50;
        return (
          <li
            key={e.id}
            onPointerEnter={() => setFocus({ entityId: e.id })}
            onPointerLeave={() => setFocus({ entityId: null })}
            className={clsx("transition-colors", entityId === e.id ? "bg-surface-2" : "hover:bg-surface-2")}
          >
            <Link href={`/companies/${e.id}`} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1.5 px-4 py-3 no-underline">
              <span className="truncate text-base font-medium text-ink">{e.name}</span>
              <span className="text-sm">
                <Delta value={e.delta} />
              </span>
              <span className="relative col-span-2 h-1.5 rounded-full bg-surface-3" aria-hidden="true">
                <span className="absolute inset-y-0 left-1/2 w-px bg-line-strong" />
                <span
                  className={clsx("absolute inset-y-0 rounded-full", delta >= 0 ? "left-1/2 bg-pos" : "right-1/2 bg-neg")}
                  style={{ width: `${w}%` }}
                />
              </span>
            </Link>
          </li>
        );
      })}
    </ol>
  );
}
