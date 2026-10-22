import Link from "next/link";

import { SentimentPill } from "@/components/ui/sentiment";
import { SourceBadge } from "@/components/ui/source-badge";
import type { EventRecord } from "@/lib/api/types";
import { fmtDayLong, fmtPct } from "@/lib/format";

/** A structured event record: what happened, to whom, from which sentence. */
export function EventCard({ event, showSourceLink = true }: { event: EventRecord; showSourceLink?: boolean }) {
  const args = Object.entries(event.arguments);
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="inline-flex h-6 items-center rounded-full bg-brand px-2.5 text-xs font-semibold text-white">{event.type}</span>
        <span className="text-sm text-ink-3">{event.group}</span>
        <span className="ml-auto">
          <SentimentPill sentiment={event.sentiment} />
        </span>
      </div>
      <div>
        {event.entityId ? (
          <Link href={`/companies/${event.entityId}`} className="text-md font-semibold text-ink no-underline hover:text-brand-ink">
            {event.entityName}
          </Link>
        ) : (
          <span className="text-md font-semibold text-ink-2" title="The order names a party that is not in the company list">
            Unresolved party
          </span>
        )}
        <p className="mt-1 text-base text-ink-2">{event.headline}</p>
      </div>
      <dl className="grid grid-cols-[minmax(0,8.5rem)_1fr] gap-x-4 gap-y-2 rounded-xl bg-surface-2 p-4 text-sm">
        <dt className="text-ink-3">Date</dt>
        <dd className="text-ink">{fmtDayLong(event.t)}</dd>
        {args.map(([k, v]) => (
          <div key={k} className="contents">
            <dt className="text-ink-3 capitalize">{k.replace(/_/g, " ")}</dt>
            <dd className="text-ink">{v}</dd>
          </div>
        ))}
        <dt className="text-ink-3">Extracted by</dt>
        <dd className="text-ink-2">{event.extractor === "llm" ? "Qwen 2.5 7B, checked against the schema" : "Rules baseline"}</dd>
        <dt className="text-ink-3">Confidence</dt>
        <dd className="num text-ink-2">{fmtPct(event.confidence)}</dd>
      </dl>
      {showSourceLink && event.documentId && (
        <p className="flex items-center gap-2 text-sm">
          <SourceBadge kind={event.source} />
          <Link href={`/filings/${event.documentId}`} className="text-brand-ink hover:underline">
            Open the filing at the sentence that triggered it
          </Link>
        </p>
      )}
    </div>
  );
}
