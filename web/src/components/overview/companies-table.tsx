"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";
import clsx from "clsx";

import { Confidence, Delta, SentimentPill } from "@/components/ui/sentiment";
import type { EntityRow } from "@/lib/api/types";
import { fmtInt } from "@/lib/format";
import { useFocus } from "./focus";

type Key = "name" | "sector" | "score" | "delta" | "mentions" | "confidence";

const COLS: { key: Key; label: string; numeric?: boolean; className?: string }[] = [
  { key: "name", label: "Company" },
  { key: "sector", label: "Sector", className: "hidden md:table-cell" },
  { key: "score", label: "Sentiment", numeric: true },
  { key: "delta", label: "Change", numeric: true, className: "hidden sm:table-cell" },
  { key: "mentions", label: "Mentions", numeric: true, className: "hidden md:table-cell" },
  { key: "confidence", label: "Confidence", numeric: true, className: "hidden lg:table-cell" },
];

export function CompaniesTable({ entities }: { entities: EntityRow[] }) {
  const [sort, setSort] = useState<{ key: Key; dir: 1 | -1 }>({ key: "delta", dir: -1 });
  const { entityId, setFocus } = useFocus();
  const router = useRouter();

  const rows = useMemo(() => {
    const out = [...entities];
    out.sort((a, b) => {
      const va = sort.key === "delta" ? Math.abs(a.delta) : a[sort.key];
      const vb = sort.key === "delta" ? Math.abs(b.delta) : b[sort.key];
      return (va < vb ? -1 : va > vb ? 1 : 0) * sort.dir;
    });
    return out;
  }, [entities, sort]);

  const toggle = (key: Key) =>
    setSort((s) => (s.key === key ? { key, dir: s.dir === 1 ? -1 : 1 } : { key, dir: key === "name" || key === "sector" ? 1 : -1 }));

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-sm">
        <caption className="sr-only">
          Companies by sentiment over the selected window. Change is sorted by size of move.
        </caption>
        <thead>
          <tr className="border-b border-line">
            {COLS.map((c) => {
              const active = sort.key === c.key;
              const Icon = !active ? ArrowUpDown : sort.dir === 1 ? ArrowUp : ArrowDown;
              return (
                <th
                  key={c.key}
                  scope="col"
                  aria-sort={active ? (sort.dir === 1 ? "ascending" : "descending") : "none"}
                  className={clsx("h-9 px-4 font-medium text-ink-3", c.numeric ? "text-right" : "text-left", c.className)}
                >
                  <button
                    type="button"
                    onClick={() => toggle(c.key)}
                    className={clsx(
                      "inline-flex items-center gap-1 rounded-s text-xs hover:text-ink",
                      c.numeric && "flex-row-reverse",
                      active && "text-ink",
                    )}
                  >
                    {c.key === "delta" && active ? "Largest change" : c.label}
                    <Icon className={clsx("size-3", !active && "opacity-40")} aria-hidden="true" />
                  </button>
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {rows.map((e) => {
            const focused = entityId === e.id;
            return (
              <tr
                key={e.id}
                onPointerEnter={() => setFocus({ entityId: e.id })}
                onPointerLeave={() => setFocus({ entityId: null })}
                onClick={() => router.push(`/companies/${e.id}`)}
                className={clsx(
                  "cursor-pointer border-b border-line transition-colors last:border-0",
                  focused ? "bg-accent-weak/60" : "hover:bg-surface-2",
                )}
              >
                <td className="px-4 py-2.5">
                  <Link
                    href={`/companies/${e.id}`}
                    onFocus={() => setFocus({ entityId: e.id })}
                    onBlur={() => setFocus({ entityId: null })}
                    className="font-medium text-ink no-underline hover:text-accent-ink"
                  >
                    {e.name}
                  </Link>
                  <span className="ml-2 font-mono text-2xs text-ink-3">{e.ticker}</span>
                </td>
                <td className="hidden px-4 py-2.5 text-ink-2 md:table-cell">{e.sector}</td>
                <td className="px-4 py-2.5 text-right">
                  <SentimentPill sentiment={e.sentiment} score={e.score} />
                </td>
                <td className="hidden px-4 py-2.5 text-right sm:table-cell">
                  <Delta value={e.delta} />
                </td>
                <td className="num hidden px-4 py-2.5 text-right text-ink-2 md:table-cell">{fmtInt(e.mentions)}</td>
                <td className="hidden px-4 py-2.5 text-right lg:table-cell">
                  <Confidence value={e.confidence} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
