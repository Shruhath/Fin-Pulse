import type { Metadata } from "next";

import { OfflineState } from "@/components/ui/states";
import { EventsWorkspace } from "@/components/workspaces/events";
import { getEvents, parseWindow } from "@/lib/api/client";
import { WINDOW_DAYS, WINDOW_LABEL } from "@/lib/format";

export const metadata: Metadata = { title: "Events" };

export default async function EventsPage(props: PageProps<"/events">) {
  const w = parseWindow((await props.searchParams).w);
  const res = await getEvents(w);
  if (res.state === "offline") return <OfflineState message={res.message} />;
  return <EventsWorkspace key={w} events={res.state === "ok" ? res.data : []} windowDays={WINDOW_DAYS[w]} windowLabel={WINDOW_LABEL[w]} />;
}
