import type { Metadata } from "next";

import { PageHeader } from "@/components/app/page-header";
import { WindowSelect } from "@/components/app/window-select";
import { CompaniesBrowser } from "@/components/pages/companies-browser";
import { OfflineState } from "@/components/ui/states";
import { getCompanies, getOverview, parseWindow } from "@/lib/api/client";
import { WINDOW_LABEL } from "@/lib/format";

export const metadata: Metadata = { title: "Companies" };

export default async function CompaniesPage(props: PageProps<"/companies">) {
  const w = parseWindow((await props.searchParams).w);
  const [list, overview] = await Promise.all([getCompanies(w), getOverview(w)]);
  if (list.state !== "ok") return <OfflineState message={list.state === "offline" ? list.message : "No companies yet."} />;
  const ov = overview.state === "ok" ? overview.data : null;
  return (
    <>
      <PageHeader
        title="Companies"
        description="How each company reads across the filings that mention it. Open one for its sentiment over time, events and checked summary."
        actions={<WindowSelect />}
      />
      <CompaniesBrowser entities={list.data} market={ov?.market ?? []} events={ov?.events ?? []} windowLabel={WINDOW_LABEL[w]} />
    </>
  );
}
