"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowDown, ArrowUp, ArrowUpDown, Search } from "lucide-react";
import clsx from "clsx";

import { useFocus } from "@/components/linked/focus";
import { Confidence, Delta, SentimentPill } from "@/components/ui/sentiment";
import { Empty } from "@/components/ui/states";
import type { EntityRow } from "@/lib/api/types";
import { fmtInt, magnitude } from "@/lib/format";

type Key = "name" | "sector" | "score" | "delta" | "mentions" | "confidence";

// Columns appear as the container gets wider, not the viewport.
const COLS: { key: Key; label: string; numeric?: boolean; className?: string }[] = [
  { key: "name", label: "Company" },
  { key: "sector", label: "Sector", className: "hidden @3xl:table-cell" },
  { key: "score", label: "Sentiment", numeric: true },
  { key: "delta", label: "Change", numeric: true, className: "hidden @md:table-cell" },
  { key: "mentions", label: "Mentions", numeric: true, className: "hidden @xl:table-cell" },
  { key: "confidence", label: "Confidence", numeric: true, className: "hidden @2xl:table-cell" },
];

const PAGE = 25;

export function CompaniesTable({ entities }: { entities: EntityRow[] }) {
  const [sort, setSort] = useState<{ key: Key; dir: 1 | -1 }>({ key: "delta", dir: -1 });
  const [query, setQuery] = useState("");
  const [shown, setShown] = useState(PAGE);
  const hasSector = entities.some((e) => e.sector);
  const cols = COLS.filter((c) => c.key !== "sector" || hasSector);
  const { entityId, setFocus } = useFocus();
  const router = useRouter();

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    const out = entities.filter((e) => !q || e.name.toLowerCase().includes(q) || e.ticker.toLowerCase().includes(q) || e.sector.toLowerCase().includes(q));
    const value = (e: EntityRow) => (sort.key === "delta" ? (e.delta === null ? null : magnitude(e.delta)) : e[sort.key]);
    out.sort((a, b) => {
      const va = value(a);
      const vb = value(b);
      if (va === null || vb === null) return va === vb ? 0 : va === null ? 1 : -1; // unscored companies last
      return (va < vb ? -1 : va > vb ? 1 : 0) * sort.dir;
    });
    return out;
  }, [entities, sort, query]);

  const toggle = (key: Key) =>
    setSort((s) => (s.key === key ? { key, dir: s.dir === 1 ? -1 : 1 } : { key, dir: key === "name" || key === "sector" ? 1 : -1 }));

  return (
    <div className="@container">
      <div className="relative mb-3 max-w-sm">
        <Search className="pointer-events-none absolute top-1/2 left-3.5 size-4 -translate-y-1/2 text-ink-3" aria-hidden="true" />
        <label htmlFor="company-search" className="sr-only">
          Find a company
        </label>
        <input
          id="company-search"
          type="search"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setShown(PAGE);
          }}
          placeholder="Find a company, ticker or sector"
          className="h-11 w-full rounded-xl border border-line bg-surface pr-3 pl-10 text-base text-ink outline-none transition-shadow focus:border-brand focus:shadow-[0_0_0_3px_var(--brand-weak)]"
        />
      </div>
      {rows.length === 0 ? (
        <Empty>No company matches “{query}”.</Empty>
      ) : (
        <div className="overflow-hidden rounded-2xl border border-line bg-surface shadow-1">
          <table className="w-full border-collapse text-base">
            <caption className="sr-only">Companies by sentiment over the selected window.</caption>
            <thead>
              <tr className="border-b border-line bg-surface-2/60">
                {cols.map((c) => {
                  const active = sort.key === c.key;
                  const Icon = !active ? ArrowUpDown : sort.dir === 1 ? ArrowUp : ArrowDown;
                  return (
                    <th
                      key={c.key}
                      scope="col"
                      aria-sort={active ? (sort.dir === 1 ? "ascending" : "descending") : "none"}
                      className={clsx("h-11 px-4 text-sm font-medium text-ink-3", c.numeric ? "text-right" : "text-left", c.className)}
                    >
                      <button type="button" onClick={() => toggle(c.key)} className={clsx("inline-flex items-center gap-1 rounded-md hover:text-ink", c.numeric && "flex-row-reverse", active && "text-ink")}>
                        {c.key === "delta" && active ? "Size of change" : c.label}
                        <Icon className={clsx("size-3.5", !active && "opacity-40")} aria-hidden="true" />
                      </button>
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {rows.slice(0, shown).map((e) => (
                <tr
                  key={e.id}
                  onPointerEnter={() => setFocus({ entityId: e.id })}
                  onPointerLeave={() => setFocus({ entityId: null })}
                  onClick={() => router.push(`/companies/${e.id}`)}
                  className={clsx("cursor-pointer border-b border-line transition-colors last:border-0", entityId === e.id ? "bg-surface-2" : "hover:bg-surface-2")}
                >
                  <td className="px-4 py-3">
                    <Link
                      href={`/companies/${e.id}`}
                      onFocus={() => setFocus({ entityId: e.id })}
                      onBlur={() => setFocus({ entityId: null })}
                      className="font-medium text-ink no-underline"
                    >
                      {e.name}
                    </Link>
                    <span className="num ml-2 text-sm text-ink-3">{e.ticker}</span>
                  </td>
                  {hasSector && <td className="hidden px-4 py-3 text-ink-2 @3xl:table-cell">{e.sector}</td>}
                  <td className="px-4 py-3 text-right">
                    <SentimentPill sentiment={e.sentiment} score={e.score} />
                  </td>
                  <td className="hidden px-4 py-3 text-right @md:table-cell">
                    <Delta value={e.delta} />
                  </td>
                  <td className="num hidden px-4 py-3 text-right text-ink-2 @xl:table-cell">{fmtInt(e.mentions)}</td>
                  <td className="hidden px-4 py-3 text-right @2xl:table-cell">
                    <Confidence value={e.confidence} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {rows.length > shown && (
        <div className="mt-5 flex justify-center">
          <button
            type="button"
            onClick={() => setShown((n) => n + PAGE)}
            className="inline-flex h-11 items-center rounded-full border border-line-strong bg-surface px-5 text-sm font-medium text-ink transition-colors hover:border-brand"
          >
            Show {Math.min(PAGE, rows.length - shown)} more of {rows.length - shown} left
          </button>
        </div>
      )}
    </div>
  );
}
