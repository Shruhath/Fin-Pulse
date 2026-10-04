"use client";

import { MarketChart } from "@/components/charts/market-chart";
import { Panel } from "@/components/ui/panel";
import { EmptyRow } from "@/components/ui/states";
import type { Overview } from "@/lib/api/types";
import { CompaniesTable } from "./companies-table";
import { FilingsFeed } from "./filings-feed";
import { FocusProvider, useFocus } from "./focus";

export function OverviewBoard({ data }: { data: Overview }) {
  return (
    <FocusProvider>
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
        <Panel
          id="market"
          title="Market sentiment"
          meta={<ChartLegend />}
          bodyClassName="px-2 pt-3 pb-1 sm:px-3"
        >
          {data.market.length > 0 ? (
            <MarketChart market={data.market} events={data.events} entities={data.entities} />
          ) : (
            <EmptyRow>No scored mentions in this window yet.</EmptyRow>
          )}
        </Panel>
        <Panel
          id="filings"
          title="Latest filings"
          meta={<span className="num">{data.filings.length} shown</span>}
          className="xl:max-h-[386px]"
          bodyClassName="overflow-y-auto"
        >
          {data.filings.length > 0 ? <FilingsFeed filings={data.filings} /> : <EmptyRow>No filings ingested yet.</EmptyRow>}
        </Panel>
      </div>
      <Panel
        id="companies"
        title="Companies"
        meta={<span className="num">{data.entities.length} tracked · hover a row to trace it on the chart</span>}
        className="mt-4"
      >
        {data.entities.length > 0 ? (
          <CompaniesTable entities={data.entities} />
        ) : (
          <EmptyRow>No companies have been resolved yet.</EmptyRow>
        )}
      </Panel>
    </FocusProvider>
  );
}

function ChartLegend() {
  const { entityId } = useFocus();
  return (
    <>
      <span className="flex items-center gap-1.5">
        <span className="h-0.5 w-4 rounded-full bg-[var(--chart-line)]" aria-hidden="true" />
        Mean
      </span>
      <span className="flex items-center gap-1.5">
        <span className="h-2.5 w-4 rounded-[2px] bg-[var(--chart-band)]" aria-hidden="true" />
        ±1σ spread
      </span>
      <span className="flex items-center gap-1.5">
        <svg viewBox="0 0 10 10" className="size-2.5" aria-hidden="true">
          <path d="M5 0 10 5 5 10 0 5Z" fill="var(--text-2)" />
        </svg>
        Event
      </span>
      {entityId && (
        <span className="flex items-center gap-1.5 text-ink">
          <span className="h-0.5 w-4 rounded-full bg-[var(--chart-focus-line)]" aria-hidden="true" />
          Selected company
        </span>
      )}
    </>
  );
}
