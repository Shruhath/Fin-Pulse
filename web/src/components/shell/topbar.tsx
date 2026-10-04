import { Suspense } from "react";

import type { CorpusStatus } from "@/lib/api/types";
import { fmtDay, fmtInt, fmtTime } from "@/lib/format";
import { CommandPalette } from "./command-palette";
import { MobileNav } from "./mobile-nav";
import { WindowControl } from "./window-control";

export function TopBar({ corpus }: { corpus: CorpusStatus | null }) {
  return (
    <header className="sticky top-0 z-30 flex h-(--topbar-h) items-center gap-3 border-b border-line bg-surface/92 px-4 backdrop-blur-sm sm:px-6">
      <MobileNav />
      <div className="min-w-0 flex-1">
        <CommandPalette />
      </div>
      <Suspense fallback={<div className="h-8 w-32" />}>
        <WindowControl />
      </Suspense>
      <CorpusBadge corpus={corpus} />
    </header>
  );
}

function CorpusBadge({ corpus }: { corpus: CorpusStatus | null }) {
  if (!corpus) {
    return (
      <p className="hidden items-center gap-2 text-xs text-ink-3 xl:flex">
        <span className="size-1.5 rounded-full bg-warn" aria-hidden="true" />
        API offline
      </p>
    );
  }
  return (
    <p className="hidden items-center gap-2 text-xs text-ink-3 xl:flex">
      <span className="size-1.5 rounded-full bg-pos" aria-hidden="true" />
      <span className="num">
        <span className="font-semibold text-ink-2">{fmtInt(corpus.documents)}</span> documents
      </span>
      {corpus.lastIngestAt && (
        <span className="num">
          · ingested {fmtDay(corpus.lastIngestAt)}, {fmtTime(corpus.lastIngestAt)}
        </span>
      )}
    </p>
  );
}
