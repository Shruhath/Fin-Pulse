import Link from "next/link";

import { SentimentPill } from "@/components/ui/sentiment";
import { SourceBadge } from "@/components/ui/source-badge";
import type { EventRecord } from "@/lib/api/types";
import { fmtDayLong, fmtPct } from "@/lib/format";

/** A structured event record: what happened, to whom, from which sentence. */
export function EventCard({ event, showSourceLink = true }: { event: EventRecord; showSourceLink?: boolean }) {
  const args = Object.entries(event.arguments);
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="border border-ring/50 px-1.5 py-0.5 font-mono text-2xs font-semibold text-accent-ink">{event.type}</span>
        <span className="font-mono text-2xs text-ink-3">{event.group.toLowerCase()}</span>
        <span className="ml-auto">
          <SentimentPill sentiment={event.sentiment} />
        </span>
      </div>
      <div>
        <Link href={`/companies/${event.entityId}`} className="text-md font-semibold text-ink no-underline hover:text-accent-ink">
          {event.entityName}
        </Link>
        <p className="mt-1 text-sm leading-snug text-ink-2">{event.headline}</p>
      </div>
      <dl className="grid grid-cols-[minmax(0,9rem)_1fr] gap-x-3 gap-y-1.5 border-t border-line pt-3 text-sm">
        <dt className="font-mono text-2xs text-ink-3">date</dt>
        <dd className="text-ink">{fmtDayLong(event.t)}</dd>
        {args.map(([k, v]) => (
          <div key={k} className="contents">
            <dt className="font-mono text-2xs text-ink-3">{k.replace(/_/g, " ")}</dt>
            <dd className="text-ink">{v}</dd>
          </div>
        ))}
        <dt className="font-mono text-2xs text-ink-3">extractor</dt>
        <dd className="text-ink-2">{event.extractor === "llm" ? "Qwen 2.5 7B, schema-validated" : "rules baseline"}</dd>
        <dt className="font-mono text-2xs text-ink-3">confidence</dt>
        <dd className="font-mono text-xs text-ink-2">{fmtPct(event.confidence)}</dd>
      </dl>
      {showSourceLink && event.documentId && (
        <p className="flex items-center gap-2 border-t border-line pt-3 text-sm">
          <SourceBadge kind={event.source} />
          <Link href={`/filings/${event.documentId}`} className="text-link hover:underline">
            Open the source filing at the trigger sentence
          </Link>
        </p>
      )}
    </div>
  );
}
