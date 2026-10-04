import type { Metadata } from "next";

import { OfflineState } from "@/components/ui/states";
import { CompaniesWorkspace } from "@/components/workspaces/companies";
import { getCompanies, getCompany, parseWindow } from "@/lib/api/client";

export async function generateMetadata(props: PageProps<"/companies/[id]">): Promise<Metadata> {
  const { id } = await props.params;
  const res = await getCompany(id, "30d");
  return { title: res.state === "ok" ? res.data.entity.name : "Company" };
}

export default async function CompanyPage(props: PageProps<"/companies/[id]">) {
  const { id } = await props.params;
  const w = parseWindow((await props.searchParams).w);
  const [list, detail] = await Promise.all([getCompanies(w), getCompany(id, w)]);
  if (list.state === "offline") return <OfflineState message={list.message} />;
  return <CompaniesWorkspace entities={list.state === "ok" ? list.data : []} detail={detail.state === "ok" ? detail.data : null} />;
}
