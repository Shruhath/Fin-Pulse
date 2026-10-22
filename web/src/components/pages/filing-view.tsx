"use client";

import { useState } from "react";
import clsx from "clsx";

import { Segmented } from "@/components/app/segmented";
import { TabBar, TabPanel, TabRoot } from "@/components/app/tab-bar";
import { EntityList } from "@/components/evidence/entity-list";
import { EventCard } from "@/components/evidence/event-card";
import { VerifiedSummary } from "@/components/evidence/claims";
import { DocReader } from "@/components/evidence/doc-reader";
import { Empty } from "@/components/ui/states";
import type { DocumentDetail } from "@/lib/api/types";

/**
 * One filing: the text with the model's marks on the left, and on the right the checks that
 * hang off it (claims against their sources, companies, events). On a narrow screen the two
 * are a switch, because side by side would squeeze both.
 */
export function FilingView({ doc, at }: { doc: DocumentDetail; at?: { start: number; end: number } | null }) {
  const [pane, setPane] = useState<"read" | "checks">("read");
  const [tab, setTab] = useState("summary");
  const claims = doc.summary?.claims.length ?? 0;
  const companies = new Set(doc.spans.map((s) => s.entityId).filter(Boolean)).size;

  return (
    <div>
      <div className="mb-6 xl:hidden">
        <Segmented
          label="Show"
          value={pane}
          onChange={setPane}
          items={[
            { value: "read", label: "Read" },
            { value: "checks", label: "Checks", count: claims },
          ]}
        />
      </div>
      <div className="grid gap-10 xl:grid-cols-[minmax(0,1fr)_410px]">
        <div className={clsx(pane === "read" ? "block" : "hidden", "min-w-0 xl:block")}>
          <DocReader doc={doc} at={at} />
        </div>
        <aside className={clsx(pane === "checks" ? "block" : "hidden", "min-w-0 xl:sticky xl:top-8 xl:block xl:self-start")}>
          <div className="overflow-hidden rounded-2xl border border-line bg-surface shadow-1 xl:max-h-[calc(100dvh-4rem)] xl:overflow-y-auto">
            <TabRoot value={tab} onValueChange={setTab}>
              <TabBar
                active={tab}
                className="px-2"
                items={[
                  { value: "summary", label: "Summary", count: claims },
                  { value: "companies", label: "Companies", count: companies },
                  { value: "events", label: "Events", count: doc.events.length },
                ]}
              />
              <TabPanel value="summary" className="px-5 pb-5">
                <VerifiedSummary summary={doc.summary} currentDocumentId={doc.id} onLocate={() => setPane("read")} />
              </TabPanel>
              <TabPanel value="companies" className="px-3 pb-4">
                <EntityList doc={doc} />
              </TabPanel>
              <TabPanel value="events" className="space-y-6 px-5 pb-5">
                {doc.events.length === 0 ? (
                  <Empty>{doc.status === "analysed" ? "No event in this filing matched the taxonomy." : "Event extraction has not run on this filing yet."}</Empty>
                ) : (
                  doc.events.map((e) => (
                    <div key={e.id} className="border-b border-line pb-6 last:border-0 last:pb-0">
                      <EventCard event={e} showSourceLink={false} />
                    </div>
                  ))
                )}
              </TabPanel>
            </TabRoot>
          </div>
        </aside>
      </div>
    </div>
  );
}
