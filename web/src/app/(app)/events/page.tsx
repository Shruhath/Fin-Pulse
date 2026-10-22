import type { Metadata } from "next";

import { PageHeader } from "@/components/app/page-header";
import { WindowSelect } from "@/components/app/window-select";
import { EventsBrowser } from "@/components/pages/events-browser";
import { OfflineState } from "@/components/ui/states";
import { getEvents, parseWindow } from "@/lib/api/client";
import { WINDOW_DAYS, WINDOW_LABEL } from "@/lib/format";

export const metadata: Metadata = { title: "Events" };

export default async function EventsPage(props: PageProps<"/events">) {
  const w = parseWindow((await props.searchParams).w);
  const res = await getEvents(w);
  if (res.state === "offline") return <OfflineState message={res.message} />;
  return (
    <>
      <PageHeader
        title="Events"
        description="Penalties, admissions, dividends and other market-moving events, pulled out of the filings as structured records."
        actions={<WindowSelect />}
      />
      <EventsBrowser key={w} events={res.state === "ok" ? res.data : []} windowDays={WINDOW_DAYS[w]} windowLabel={WINDOW_LABEL[w]} />
    </>
  );
}
