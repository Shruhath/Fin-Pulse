"use client";

import { useState } from "react";

import { PageHeader } from "@/components/app/page-header";
import { TabBar, TabPanel, TabRoot } from "@/components/app/tab-bar";
import { EntityChart } from "@/components/charts/entity-chart";
import { EventCard } from "@/components/evidence/event-card";
import { Mentions } from "@/components/evidence/mentions";
import { VerifiedSummary } from "@/components/evidence/claims";
import { Confidence, Delta, SentimentPill } from "@/components/ui/sentiment";
import { Empty } from "@/components/ui/states";
import type { CompanyDetail } from "@/lib/api/types";
import { fmtInt } from "@/lib/format";

/** One company: how it reads, what happened, and what the filings say, in three tabs. */
export function CompanyView({ detail, actions }: { detail: CompanyDetail; actions: React.ReactNode }) {
  const [tab, setTab] = useState("overview");
  const e = detail.entity;
  return (
    <>
      <PageHeader
        back={{ href: "/companies", label: "Companies" }}
        title={e.name}
        description={
          <>
            {[e.ticker, e.sector].filter(Boolean).join(" · ")}
            {detail.aliases.length > 0 && <>{e.ticker || e.sector ? " · " : ""}also written as {detail.aliases.slice(0, 4).join(", ")}</>}
          </>
        }
        actions={actions}
      />
      <dl className="mb-8 flex flex-wrap items-center gap-x-8 gap-y-3 rounded-2xl border border-line bg-surface px-5 py-4 shadow-1">
        <div>
          <dt className="text-sm text-ink-3">Reads as</dt>
          <dd className="mt-1">
            <SentimentPill sentiment={e.sentiment} score={e.score} />
          </dd>
        </div>
        <div>
          <dt className="text-sm text-ink-3">Change in the window</dt>
          <dd className="mt-1 text-base">
            <Delta value={e.delta} />
          </dd>
        </div>
        <div>
          <dt className="text-sm text-ink-3">Mentions</dt>
          <dd className="num mt-1 text-base font-semibold text-ink">{fmtInt(e.mentions)}</dd>
        </div>
        <div>
          <dt className="text-sm text-ink-3">Confidence</dt>
          <dd className="mt-1">
            <Confidence value={e.confidence} />
          </dd>
        </div>
      </dl>

      <TabRoot value={tab} onValueChange={setTab}>
        <TabBar
          active={tab}
          items={[
            { value: "overview", label: "Overview" },
            { value: "events", label: "Events", count: detail.events.length },
            { value: "mentions", label: "Mentions", count: detail.mentions.length },
          ]}
        />
        <TabPanel value="overview" className="space-y-10">
          <section>
            <h2 className="mb-3 text-lg font-semibold text-ink">Sentiment over time</h2>
            <div className="h-[300px] rounded-2xl border border-line bg-surface p-3 shadow-1">
              <EntityChart series={e.series} events={detail.events} name={e.name} />
            </div>
          </section>
          <section>
            <h2 className="mb-3 text-lg font-semibold text-ink">What the filings say</h2>
            <div className="max-w-[78ch]">
              <VerifiedSummary summary={detail.summary} />
            </div>
          </section>
        </TabPanel>
        <TabPanel value="events">
          {detail.events.length ? (
            <div className="grid gap-5 md:grid-cols-2">
              {detail.events.map((ev) => (
                <div key={ev.id} className="rounded-2xl border border-line bg-surface p-5 shadow-1">
                  <EventCard event={ev} />
                </div>
              ))}
            </div>
          ) : (
            <Empty>No events were extracted for this company.</Empty>
          )}
        </TabPanel>
        <TabPanel value="mentions">
          <Mentions mentions={detail.mentions} />
        </TabPanel>
      </TabRoot>
    </>
  );
}
