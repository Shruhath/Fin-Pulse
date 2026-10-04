"use client";

import { HeatmapLegend, MarketHeatmap } from "@/components/charts/market-heatmap";
import { FilingsFeed } from "@/components/overview/filings-feed";
import { Movers } from "@/components/tiles/movers";
import { SourceMix } from "@/components/tiles/source-mix";
import { Empty } from "@/components/ui/states";
import { Workspace } from "@/components/wm/workspace";
import type { Overview } from "@/lib/api/types";
import { fmtScore } from "@/lib/format";

export function OverviewWorkspace({ data, windowLabel }: { data: Overview; windowLabel: string }) {
  const mean = data.market.length ? data.market.reduce((a, p) => a + p.mean, 0) / data.market.length : 0;
  const spread = data.market.length ? data.market.reduce((a, p) => a + p.std, 0) / data.market.length : 0;
  return (
    <Workspace
      tiles={[
        {
          id: "market",
          cls: "chart",
          title: `companies × days · ${windowLabel}`,
          flush: true,
          mobileMinH: 340,
          meta: data.market.length ? (
            <>
              <HeatmapLegend />
              <span className="hidden font-mono xl:inline">
                mean <b className="text-ink">{fmtScore(mean)}</b> · ±{spread.toFixed(2)}
              </span>
            </>
          ) : null,
          node: data.market.length ? (
            <div className="h-full pt-3 pr-1">
              <MarketHeatmap market={data.market} events={data.events} entities={data.entities} />
            </div>
          ) : (
            <Empty>No scored mentions in this window yet.</Empty>
          ),
        },
        {
          id: "filings",
          cls: "feed",
          title: "latest filings",
          weight: 2.1,
          flush: true,
          meta: <span className="font-mono">{data.filings.length}</span>,
          node: data.filings.length ? <FilingsFeed filings={data.filings} /> : <Empty>No filings ingested yet.</Empty>,
        },
        {
          id: "movers",
          cls: "list",
          title: "largest moves",
          weight: 1.25,
          flush: true,
          node: data.entities.length ? <Movers entities={data.entities} /> : <Empty>No companies scored yet.</Empty>,
        },
        {
          id: "sources",
          cls: "bars",
          title: "corpus by source",
          weight: 0.95,
          flush: true,
          node: <SourceMix sources={data.sources} />,
        },
      ]}
    />
  );
}
