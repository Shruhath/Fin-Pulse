"use client";

import { useState } from "react";

import { TabBar, TabPanel, TabRoot } from "@/components/app/tab-bar";
import { HeatmapLegend, MarketHeatmap } from "@/components/charts/market-heatmap";
import { CompaniesTable } from "@/components/lists/companies-table";
import { Empty } from "@/components/ui/states";
import type { EntityRow, EventMarker, MarketPoint } from "@/lib/api/types";
import { fmtScore } from "@/lib/format";

/** Every tracked company, as a list you can search or as one map of the whole window. */
export function CompaniesBrowser({ entities, market, events, windowLabel }: { entities: EntityRow[]; market: MarketPoint[]; events: EventMarker[]; windowLabel: string }) {
  const [tab, setTab] = useState("list");
  const mean = market.length ? market.reduce((a, p) => a + p.mean, 0) / market.length : 0;
  const spread = market.length ? market.reduce((a, p) => a + p.std, 0) / market.length : 0;
  return (
    <TabRoot value={tab} onValueChange={setTab}>
      <TabBar
        active={tab}
        items={[
          { value: "list", label: "Companies", count: entities.length },
          { value: "map", label: "Sentiment map" },
        ]}
      />
      <TabPanel value="list">{entities.length ? <CompaniesTable entities={entities} /> : <Empty>No companies have been resolved yet.</Empty>}</TabPanel>
      <TabPanel value="map">
        {market.length ? (
          <div className="rounded-2xl border border-line bg-surface p-5 shadow-1">
            <div className="mb-3 flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2">
              <p className="text-sm text-ink-2">
                Each row is a company and each column a day, over the {windowLabel}. The market averaged{" "}
                <span className="num font-semibold text-ink">{fmtScore(mean)}</span> with a spread of ±{spread.toFixed(2)}.
              </p>
              <HeatmapLegend />
            </div>
            <div style={{ height: Math.max(560, 120 + entities.length * 22) }}>
              <MarketHeatmap market={market} events={events} entities={entities} />
            </div>
          </div>
        ) : (
          <Empty>No scored mentions in this window yet.</Empty>
        )}
      </TabPanel>
    </TabRoot>
  );
}
