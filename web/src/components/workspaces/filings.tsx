"use client";

import { FilingsFeed } from "@/components/overview/filings-feed";
import { DocReader } from "@/components/tiles/doc-reader";
import { EntityInspector } from "@/components/tiles/entity-inspector";
import { VerifiedSummary } from "@/components/tiles/verified-summary";
import { Empty, Missing } from "@/components/ui/states";
import { Workspace } from "@/components/wm/workspace";
import type { DocumentDetail, FilingItem } from "@/lib/api/types";

export function FilingsWorkspace({ filings, doc }: { filings: FilingItem[]; doc: DocumentDetail | null }) {
  return (
    <Workspace
      tiles={[
        {
          id: "reader",
          mobileOrder: 1,
          cls: "reader",
          title: doc ? doc.title.toLowerCase() : "reader",
          mobileMinH: 420,
          node: doc ? <DocReader doc={doc} /> : <Missing what="filing" />,
        },
        {
          id: "filing-list",
          mobileOrder: 4,
          cls: "feed",
          title: "filings",
          flush: true,
          weight: 1.3,
          meta: <span className="font-mono">{filings.length}</span>,
          node: filings.length ? <FilingsFeed filings={filings} selectedId={doc?.id} /> : <Empty>No filings ingested yet.</Empty>,
        },
        {
          id: "inspect",
          mobileOrder: 3,
          cls: "inspect",
          title: "entities and events",
          weight: 1.2,
          flush: true,
          node: doc ? <EntityInspector doc={doc} /> : <Empty>Pick a filing.</Empty>,
        },
        {
          id: "filing-claims",
          mobileOrder: 2,
          cls: "claims",
          title: "verified summary",
          weight: 1.3,
          flush: true,
          node: <VerifiedSummary summary={doc?.summary ?? null} currentDocumentId={doc?.id} />,
        },
      ]}
    />
  );
}
