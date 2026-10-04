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
      className="inline-flex h-5 min-w-10 items-center justify-center rounded-s border border-line bg-surface-2 px-1.5 font-mono text-2xs font-medium text-ink-2 no-underline"
    >
      {kind}
    </abbr>
  );
}
