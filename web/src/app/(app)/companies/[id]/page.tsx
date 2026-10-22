import type { Metadata } from "next";

import { PageHeader } from "@/components/app/page-header";
import { WindowSelect } from "@/components/app/window-select";
import { CompanyView } from "@/components/pages/company-view";
import { OfflineState } from "@/components/ui/states";
import { Empty } from "@/components/ui/states";
import { getCompany, parseWindow } from "@/lib/api/client";

export async function generateMetadata(props: PageProps<"/companies/[id]">): Promise<Metadata> {
  const { id } = await props.params;
  const res = await getCompany(id, "30d");
  return { title: res.state === "ok" ? res.data.entity.name : "Company" };
}

export default async function CompanyPage(props: PageProps<"/companies/[id]">) {
  const { id } = await props.params;
  const w = parseWindow((await props.searchParams).w);
  const detail = await getCompany(id, w);
  if (detail.state === "offline") return <OfflineState message={detail.message} />;
  if (detail.state === "missing") {
    return (
      <>
        <PageHeader title="Company not found" back={{ href: "/companies", label: "Companies" }} />
        <Empty>That company is not in the corpus. Pick another from the list.</Empty>
      </>
    );
  }
  return <CompanyView detail={detail.data} actions={<WindowSelect />} />;
}
