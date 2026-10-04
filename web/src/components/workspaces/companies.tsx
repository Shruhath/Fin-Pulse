"use client";

import { EntityChart } from "@/components/charts/entity-chart";
import { CompaniesTable } from "@/components/overview/companies-table";
import { EventCard } from "@/components/tiles/event-card";
import { Mentions } from "@/components/tiles/mentions";
import { VerifiedSummary } from "@/components/tiles/verified-summary";
import { Confidence, Delta, SentimentPill } from "@/components/ui/sentiment";
import { Empty, Missing } from "@/components/ui/states";
import { Workspace } from "@/components/wm/workspace";
import type { CompanyDetail, EntityRow } from "@/lib/api/types";
import { fmtInt } from "@/lib/format";

export function CompaniesWorkspace({ entities, detail }: { entities: EntityRow[]; detail: CompanyDetail | null }) {
  const e = detail?.entity;
  return (
    <Workspace
      tiles={[
        {
          id: "companies",
          cls: "table",
          title: "companies",
          flush: true,
          mobileMinH: 320,
          meta: <span className="font-mono">{entities.length} tracked</span>,
          node: entities.length ? <CompaniesTable entities={entities} selectedId={e?.id} /> : <Empty>No companies resolved yet.</Empty>,
        },
        {
          id: "company-chart",
          cls: "chart",
          title: e ? `${e.name.toLowerCase()} · sentiment` : "company · sentiment",
          weight: 1.5,
          flush: true,
          mobileMinH: 300,
          node: e ? (
            <div className="flex h-full flex-col">
              <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-line px-3 py-2">
                <h1 className="text-md font-semibold text-ink">{e.name}</h1>
                <span className="font-mono text-2xs text-ink-3">
                  {e.ticker} · {e.sector}
                </span>
                <SentimentPill sentiment={e.sentiment} score={e.score} />
                <span className="font-mono text-xs text-ink-3">
                  change <Delta value={e.delta} />
                </span>
                <span className="font-mono text-xs text-ink-3">{fmtInt(e.mentions)} mentions</span>
                <Confidence value={e.confidence} />
              </div>
              {detail.aliases.length > 0 && (
                <p className="truncate px-3 pt-1.5 font-mono text-2xs text-ink-3">aka {detail.aliases.join(" · ")}</p>
              )}
              <div className="min-h-0 flex-1 px-1">
                <EntityChart series={e.series} events={detail.events} name={e.name} />
              </div>
            </div>
          ) : (
            <Missing what="company" />
          ),
        },
        {
          id: "company-claims",
          cls: "claims",
          title: "verified summary",
          weight: 1.4,
          flush: true,
          node: <VerifiedSummary summary={detail?.summary ?? null} />,
        },
        {
          id: "company-events",
          cls: "log",
          title: "events",
          weight: 1,
          meta: <span className="font-mono">{detail?.events.length ?? 0}</span>,
          node:
            detail && detail.events.length > 0 ? (
              <div className="space-y-6">
                {detail.events.map((ev) => (
                  <EventCard key={ev.id} event={ev} />
                ))}
              </div>
            ) : (
              <Empty>No events extracted for this company.</Empty>
            ),
        },
        {
          id: "company-mentions",
          cls: "grep",
          title: "mentions",
          weight: 1,
          flush: true,
          meta: <span className="font-mono">{detail?.mentions.length ?? 0}</span>,
          node: detail ? <Mentions mentions={detail.mentions} /> : <Empty>Pick a company.</Empty>,
        },
      ]}
    />
  );
}
