import type { Metadata } from "next";

import { OfflineState } from "@/components/ui/states";
import { FilingsWorkspace } from "@/components/workspaces/filings";
import { getDocument, getFilings } from "@/lib/api/client";

export async function generateMetadata(props: PageProps<"/filings/[id]">): Promise<Metadata> {
  const { id } = await props.params;
  const res = await getDocument(id);
  return { title: res.state === "ok" ? res.data.title : "Filing" };
}

export default async function FilingPage(props: PageProps<"/filings/[id]">) {
  const { id } = await props.params;
  const [list, doc] = await Promise.all([getFilings(), getDocument(id)]);
  if (list.state === "offline") return <OfflineState message={list.message} />;
  return <FilingsWorkspace filings={list.state === "ok" ? list.data : []} doc={doc.state === "ok" ? doc.data : null} />;
}
