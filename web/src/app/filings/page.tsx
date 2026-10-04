import type { Metadata } from "next";

import { OfflineState } from "@/components/ui/states";
import { FilingsWorkspace } from "@/components/workspaces/filings";
import { getDocument, getFilings } from "@/lib/api/client";

export const metadata: Metadata = { title: "Filings" };

export default async function FilingsPage() {
  const list = await getFilings();
  if (list.state !== "ok") return <OfflineState message={list.state === "offline" ? list.message : "No filings yet."} />;
  const first = list.data.find((f) => f.status === "analysed") ?? list.data[0];
  const doc = first ? await getDocument(first.id) : null;
  return <FilingsWorkspace filings={list.data} doc={doc?.state === "ok" ? doc.data : null} />;
}
