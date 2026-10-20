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
  const [list, doc, query] = await Promise.all([getFilings(), getDocument(id), props.searchParams]);
  if (list.state === "offline") return <OfflineState message={list.message} />;
  // ?at=start-end names a sentence of the filing, e.g. the evidence for a claim
  const match = /^(\d+)-(\d+)$/.exec(typeof query.at === "string" ? query.at : "");
  const at = match ? { start: Number(match[1]), end: Number(match[2]) } : null;
  return <FilingsWorkspace filings={list.state === "ok" ? list.data : []} doc={doc.state === "ok" ? doc.data : null} at={at} />;
}
