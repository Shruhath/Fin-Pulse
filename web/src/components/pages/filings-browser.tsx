"use client";

import { useMemo, useState } from "react";
import { Search } from "lucide-react";

import { Segmented } from "@/components/app/segmented";
import { FilingList } from "@/components/lists/filing-row";
import { Empty } from "@/components/ui/states";
import type { FilingItem, SourceKind } from "@/lib/api/types";

const PAGE = 25;
const LABEL: Record<SourceKind, string> = { SEBI: "SEBI", NCLT: "NCLT", RBI: "RBI", BSE: "BSE", NSE: "NSE", NEWS: "News" };

/** Filings by publisher, with a search box. Shows a page at a time so the list stays quick. */
export function FilingsBrowser({ filings }: { filings: FilingItem[] }) {
  const [source, setSource] = useState<SourceKind | "all">("all");
  const [query, setQuery] = useState("");
  const [shown, setShown] = useState(PAGE);

  const counts = useMemo(() => {
    const c = new Map<SourceKind, number>();
    for (const f of filings) c.set(f.source, (c.get(f.source) ?? 0) + 1);
    return c;
  }, [filings]);

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    return filings.filter(
      (f) => (source === "all" || f.source === source) && (!q || f.title.toLowerCase().includes(q) || f.entities.some((e) => e.name.toLowerCase().includes(q))),
    );
  }, [filings, source, query]);

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-center gap-3">
        <div className="relative min-w-[240px] flex-1 sm:max-w-sm">
          <Search className="pointer-events-none absolute top-1/2 left-3.5 size-4 -translate-y-1/2 text-ink-3" aria-hidden="true" />
          <label htmlFor="filing-search" className="sr-only">
            Search filings
          </label>
          <input
            id="filing-search"
            type="search"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setShown(PAGE);
            }}
            placeholder="Search by title or company"
            className="h-11 w-full rounded-xl border border-line bg-surface pr-3 pl-10 text-base text-ink outline-none transition-shadow focus:border-brand focus:shadow-[0_0_0_3px_var(--brand-weak)]"
          />
        </div>
        <div className="max-w-full overflow-x-auto">
          <Segmented
            label="Publisher"
            value={source}
            onChange={(v) => {
              setSource(v);
              setShown(PAGE);
            }}
            items={[
              { value: "all" as const, label: "All", count: filings.length },
              ...[...counts].map(([k, n]) => ({ value: k, label: LABEL[k], count: n })),
            ]}
          />
        </div>
      </div>
      {rows.length === 0 ? (
        <Empty>No filing matches that search.</Empty>
      ) : (
        <>
          <FilingList filings={rows.slice(0, shown)} />
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
        </>
      )}
    </div>
  );
}
