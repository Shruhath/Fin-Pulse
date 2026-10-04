import type { Metadata } from "next";

import { OfflineState } from "@/components/ui/states";
import { CompaniesWorkspace } from "@/components/workspaces/companies";
import { getCompanies, getCompany, parseWindow } from "@/lib/api/client";

export const metadata: Metadata = { title: "Companies" };

export default async function CompaniesPage(props: PageProps<"/companies">) {
  const w = parseWindow((await props.searchParams).w);
  const list = await getCompanies(w);
  if (list.state !== "ok") return <OfflineState message={list.state === "offline" ? list.message : "No companies yet."} />;
  // with nothing selected, open the company with the largest move
  const top = [...list.data].sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta))[0];
  const detail = top ? await getCompany(top.id, w) : null;
  return <CompaniesWorkspace entities={list.data} detail={detail?.state === "ok" ? detail.data : null} />;
}
