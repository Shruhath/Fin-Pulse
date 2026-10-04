import type { SourceKind } from "@/lib/api/types";

const NAMES: Record<SourceKind, string> = {
  BSE: "BSE announcement",
  NSE: "NSE filing",
  SEBI: "SEBI order",
  RBI: "RBI release",
  NCLT: "NCLT order",
  NEWS: "News",
};

export function SourceBadge({ kind }: { kind: SourceKind }) {
  return (
    <abbr
      title={NAMES[kind]}
      className="inline-flex h-[18px] min-w-10 items-center justify-center border border-line-strong px-1 font-mono text-[10px] font-semibold text-ink-2 no-underline"
    >
      {kind}
    </abbr>
  );
}
