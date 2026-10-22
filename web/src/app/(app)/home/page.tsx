import type { Metadata } from "next";
import Link from "next/link";

import { Section, PageHeader } from "@/components/app/page-header";
import { WindowSelect } from "@/components/app/window-select";
import { EventGlance } from "@/components/lists/event-glance";
import { FilingList } from "@/components/lists/filing-row";
import { Movers } from "@/components/lists/movers";
import { AskBar } from "@/components/pages/ask-bar";
import { Empty, OfflineState } from "@/components/ui/states";
import { getAskSuggestions, getOverview, parseWindow } from "@/lib/api/client";
import { fmtInt, WINDOW_LABEL } from "@/lib/format";

export const metadata: Metadata = { title: "Home" };

export default async function HomePage(props: PageProps<"/home">) {
  const w = parseWindow((await props.searchParams).w);
  const [res, suggestions] = await Promise.all([getOverview(w), getAskSuggestions()]);
  if (res.state !== "ok") return <OfflineState message={res.state === "offline" ? res.message : "The overview is empty."} />;
  const { corpus, entities } = res.data;
  // filings the pipeline has read come first: they carry companies and sentiment, the others are still waiting
  const filings = [...res.data.filings].sort((a, b) => Number(b.status === "analysed") - Number(a.status === "analysed"));
  const events = [...res.data.events].sort((a, b) => (b.t ?? "").localeCompare(a.t ?? ""));
  const link = "text-brand-ink no-underline hover:underline";

  return (
    <>
      <PageHeader
        title="Home"
        description={`${fmtInt(corpus.documents)} filings and ${fmtInt(corpus.entities)} companies, read on this computer. Showing the ${WINDOW_LABEL[w]}.`}
        actions={<WindowSelect />}
      />
      <AskBar suggestions={suggestions.state === "ok" ? suggestions.data : []} />

      <div className="mt-12 grid gap-12 lg:grid-cols-[minmax(0,1fr)_340px]">
        <Section
          title="Latest filings"
          aside={
            <Link href="/filings" className={link}>
              See all filings
            </Link>
          }
        >
          {filings.length ? <FilingList filings={filings.slice(0, 8)} compact /> : <Empty>No filings have been ingested yet.</Empty>}
        </Section>

        <div className="space-y-12">
          <Section
            title="Biggest sentiment moves"
            aside={
              <Link href={`/companies${w === "30d" ? "" : `?w=${w}`}`} className={link}>
                All companies
              </Link>
            }
          >
            {entities.length ? <Movers entities={entities} limit={5} /> : <Empty>No companies have been scored yet.</Empty>}
          </Section>
          <Section
            title="Latest events"
            aside={
              <Link href="/events" className={link}>
                See all
              </Link>
            }
          >
            {events.length ? <EventGlance events={events.slice(0, 4)} /> : <Empty>No events were extracted in this window.</Empty>}
          </Section>
        </div>
      </div>
    </>
  );
}
