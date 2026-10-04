import Link from "next/link";
import clsx from "clsx";

import { SentimentIcon } from "@/components/ui/sentiment";
import { SourceBadge } from "@/components/ui/source-badge";
import { Empty } from "@/components/ui/states";
import type { Mention } from "@/lib/api/types";
import { fmtDay, fmtPct } from "@/lib/format";

/** Every sentence the company was found in, with the mention cut by offsets. */
export function Mentions({ mentions }: { mentions: Mention[] }) {
  if (mentions.length === 0) return <Empty>No mentions in analysed filings yet.</Empty>;
  return (
    <ol className="divide-y divide-line">
      {mentions.map((m, i) => (
        <li key={`${m.documentId}-${i}`} className="px-3 py-2.5">
          <p className="text-sm leading-relaxed text-ink-2">
            {m.sentence.slice(0, m.start)}
            <mark
              className={clsx(
                "border-b-2 bg-transparent px-px font-medium text-ink",
                m.sentiment === "positive" ? "border-pos bg-pos-weak" : m.sentiment === "negative" ? "border-neg bg-neg-weak" : "border-neu bg-neu-weak",
              )}
            >
              {m.sentence.slice(m.start, m.end)}
              <SentimentIcon sentiment={m.sentiment} className="ml-0.5 inline size-3 -translate-y-px" />
            </mark>
            {m.sentence.slice(m.end)}
          </p>
          <p className="mt-1.5 flex items-center gap-2 font-mono text-2xs text-ink-3">
            <SourceBadge kind={m.source} />
            <span>{fmtDay(m.publishedAt)}</span>
            <span>conf {fmtPct(m.confidence)}</span>
            <Link href={`/filings/${m.documentId}`} className="ml-auto truncate text-link hover:underline">
              open filing
            </Link>
          </p>
        </li>
      ))}
    </ol>
  );
}
