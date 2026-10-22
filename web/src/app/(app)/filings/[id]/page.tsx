import type { Metadata } from "next";
import Link from "next/link";
import { ChevronLeft } from "lucide-react";

import { FilingView } from "@/components/pages/filing-view";
import { Empty, OfflineState } from "@/components/ui/states";
import { getDocument } from "@/lib/api/client";

export async function generateMetadata(props: PageProps<"/filings/[id]">): Promise<Metadata> {
  const { id } = await props.params;
  const res = await getDocument(id);
  return { title: res.state === "ok" ? res.data.title : "Filing" };
}

export default async function FilingPage(props: PageProps<"/filings/[id]">) {
  const { id } = await props.params;
  const [doc, query] = await Promise.all([getDocument(id), props.searchParams]);
  if (doc.state === "offline") return <OfflineState message={doc.message} />;
  // ?at=start-end names a sentence of the filing, e.g. the evidence for a claim
  const match = /^(\d+)-(\d+)$/.exec(typeof query.at === "string" ? query.at : "");
  const at = match ? { start: Number(match[1]), end: Number(match[2]) } : null;
  return (
    <>
      <Link href="/filings" className="-ml-1 mb-4 inline-flex items-center gap-0.5 rounded-full py-1 pr-2 pl-1 text-sm font-medium text-ink-3 no-underline transition-colors hover:text-ink">
        <ChevronLeft className="size-4" aria-hidden="true" />
        Filings
      </Link>
      {doc.state === "ok" ? <FilingView doc={doc.data} at={at} /> : <Empty>That filing is not in the corpus. Pick another from the list.</Empty>}
    </>
  );
}
