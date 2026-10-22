import type { Metadata } from "next";

import { PageHeader } from "@/components/app/page-header";
import { FilingsBrowser } from "@/components/pages/filings-browser";
import { OfflineState } from "@/components/ui/states";
import { getFilings } from "@/lib/api/client";

export const metadata: Metadata = { title: "Filings" };

export default async function FilingsPage() {
  const list = await getFilings();
  if (list.state !== "ok") return <OfflineState message={list.state === "offline" ? list.message : "No filings yet."} />;
  return (
    <>
      <PageHeader title="Filings" description="Every order, release and announcement in the corpus. Open one to read it with the companies, events and checked claims marked up." />
      <FilingsBrowser filings={list.data} />
    </>
  );
}
