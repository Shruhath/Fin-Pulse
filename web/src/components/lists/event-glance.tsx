import Link from "next/link";

import { SourceBadge } from "@/components/ui/source-badge";
import type { EventMarker } from "@/lib/api/types";
import { fmtDay } from "@/lib/format";

/** The newest extracted events, one tap from the filing that triggered each. */
export function EventGlance({ events }: { events: EventMarker[] }) {
  return (
    <ul className="divide-y divide-line overflow-hidden rounded-2xl border border-line bg-surface shadow-1">
      {events.map((e) => (
        <li key={e.id}>
          <Link href={`/filings/${e.documentId}`} className="block px-4 py-3 no-underline transition-colors hover:bg-surface-2">
            <span className="flex items-center gap-2 text-sm text-ink-3">
              <SourceBadge kind={e.source} />
              <span className="font-semibold text-brand-ink">{e.type}</span>
              <time className="ml-auto" dateTime={e.t ?? undefined}>
                {fmtDay(e.t)}
              </time>
            </span>
            <span className="mt-1 block text-base leading-6 font-medium text-ink">{e.entityName ?? "Unresolved party"}</span>
            <span className="line-clamp-2 text-sm text-ink-2">{e.headline}</span>
          </Link>
        </li>
      ))}
    </ul>
  );
}
