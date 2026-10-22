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
        <li key={`${m.documentId}-${i}`} className="py-4">
          <p className="max-w-[72ch] text-base leading-7 text-ink-2">
            {m.sentence.slice(0, m.start)}
            <mark
              className={clsx(
                "rounded-[5px] bg-transparent px-0.5 font-medium text-ink underline decoration-2 underline-offset-4",
                m.sentiment === "positive" ? "decoration-pos bg-pos-weak" : m.sentiment === "negative" ? "decoration-neg bg-neg-weak" : "decoration-neu bg-neu-weak",
              )}
            >
              {m.sentence.slice(m.start, m.end)}
              <SentimentIcon sentiment={m.sentiment} className="ml-0.5 inline size-3.5 -translate-y-px" />
            </mark>
            {m.sentence.slice(m.end)}
          </p>
          <p className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-ink-3">
            <SourceBadge kind={m.source} />
            <span>{fmtDay(m.publishedAt)}</span>
            <span>confidence {fmtPct(m.confidence)}</span>
            <Link href={`/filings/${m.documentId}`} className="text-brand-ink hover:underline sm:ml-auto">
              Open filing
            </Link>
          </p>
        </li>
      ))}
    </ol>
  );
}
