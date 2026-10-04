"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";
import clsx from "clsx";

import { useFocus } from "@/components/linked/focus";
import { Confidence, Delta, SentimentPill } from "@/components/ui/sentiment";
import type { EntityRow } from "@/lib/api/types";
import { fmtInt } from "@/lib/format";

type Key = "name" | "sector" | "score" | "delta" | "mentions" | "confidence";

// Columns appear as the window gets wider (container queries, not viewport).
const COLS: { key: Key; label: string; numeric?: boolean; className?: string }[] = [
  { key: "name", label: "Company" },
  { key: "sector", label: "Sector", className: "hidden @3xl:table-cell" },
  { key: "score", label: "Sentiment", numeric: true },
  { key: "delta", label: "Change", numeric: true, className: "hidden @md:table-cell" },
  { key: "mentions", label: "Mentions", numeric: true, className: "hidden @xl:table-cell" },
  { key: "confidence", label: "Confidence", numeric: true, className: "hidden @2xl:table-cell" },
];

export function CompaniesTable({ entities, selectedId }: { entities: EntityRow[]; selectedId?: string }) {
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
    <table className="w-full border-collapse text-sm">
      <caption className="sr-only">Companies by sentiment over the selected window.</caption>
      <thead className="sticky top-0 z-[1] bg-surface">
        <tr className="border-b border-line">
          {COLS.map((c) => {
            const active = sort.key === c.key;
            const Icon = !active ? ArrowUpDown : sort.dir === 1 ? ArrowUp : ArrowDown;
            return (
              <th
                key={c.key}
                scope="col"
                aria-sort={active ? (sort.dir === 1 ? "ascending" : "descending") : "none"}
                className={clsx("h-8 px-3 font-mono text-2xs font-medium text-ink-3", c.numeric ? "text-right" : "text-left", c.className)}
              >
                <button
                  type="button"
                  onClick={() => toggle(c.key)}
                  className={clsx("inline-flex items-center gap-1 hover:text-ink", c.numeric && "flex-row-reverse", active && "text-ink")}
                >
                  {c.key === "delta" && active ? "|change|" : c.label.toLowerCase()}
                  <Icon className={clsx("size-3", !active && "opacity-40")} aria-hidden="true" />
                </button>
              </th>
            );
          })}
        </tr>
      </thead>
      <tbody>
        {rows.map((e) => {
          const lit = entityId === e.id;
          const selected = selectedId === e.id;
          return (
            <tr
              key={e.id}
              onPointerEnter={() => setFocus({ entityId: e.id })}
              onPointerLeave={() => setFocus({ entityId: null })}
              onClick={() => router.push(`/companies/${e.id}`, { scroll: false })}
              aria-selected={selected || undefined}
              className={clsx(
                "cursor-pointer border-b border-line transition-colors last:border-0",
                selected ? "bg-accent-weak" : lit ? "bg-surface-2" : "hover:bg-surface-2",
              )}
            >
              <td className={clsx("relative px-3 py-2", selected && "shadow-[inset_2px_0_0_var(--accent)]")}>
                <Link
                  href={`/companies/${e.id}`}
                  scroll={false}
                  onFocus={() => setFocus({ entityId: e.id })}
                  onBlur={() => setFocus({ entityId: null })}
                  className="font-medium text-ink no-underline hover:text-accent-ink"
                >
                  {e.name}
                </Link>
                <span className="ml-2 font-mono text-2xs text-ink-3">{e.ticker}</span>
              </td>
              <td className="hidden px-3 py-2 text-ink-2 @3xl:table-cell">{e.sector}</td>
              <td className="px-3 py-2 text-right">
                <SentimentPill sentiment={e.sentiment} score={e.score} />
              </td>
              <td className="hidden px-3 py-2 text-right font-mono text-xs @md:table-cell">
                <Delta value={e.delta} />
              </td>
              <td className="hidden px-3 py-2 text-right font-mono text-xs text-ink-2 @xl:table-cell">{fmtInt(e.mentions)}</td>
              <td className="hidden px-3 py-2 text-right @2xl:table-cell">
                <Confidence value={e.confidence} />
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
