import type { SourceCount, SourceKind } from "@/lib/api/types";
import { fmtInt, fmtPct } from "@/lib/format";

const NAMES: Record<SourceKind, string> = {
  BSE: "BSE announcements",
  NSE: "NSE filings",
  SEBI: "SEBI orders",
  RBI: "RBI releases",
  NCLT: "NCLT orders",
  NEWS: "News (RSS)",
};

/** Where the corpus comes from: one proportional bar per source. */
export function SourceMix({ sources }: { sources: SourceCount[] }) {
  const total = sources.reduce((a, s) => a + s.documents, 0) || 1;
  const max = Math.max(...sources.map((s) => s.documents), 1);
  return (
    <div className="space-y-2.5 px-3 py-3">
      {sources.map((s) => (
        <div key={s.kind} className="grid grid-cols-[42px_minmax(0,1fr)_auto] items-center gap-3">
          <abbr title={NAMES[s.kind]} className="font-mono text-2xs font-semibold text-ink-2 no-underline">
            {s.kind}
          </abbr>
          <span className="h-2 bg-surface-2" aria-hidden="true">
            <span className="block h-full bg-info" style={{ width: `${(s.documents / max) * 100}%` }} />
          </span>
          <span className="font-mono text-xs text-ink-2">
            {fmtInt(s.documents)} <span className="text-ink-3">{fmtPct(s.documents / total)}</span>
          </span>
        </div>
      ))}
      <p className="border-t border-line pt-2 font-mono text-2xs text-ink-3">
        {fmtInt(total)} documents · public sources only
      </p>
    </div>
  );
}
