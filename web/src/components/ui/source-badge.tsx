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
      className="inline-flex h-5 min-w-11 items-center justify-center rounded-md bg-surface-3 px-1.5 text-[0.6875rem] font-bold tracking-wide text-ink-2 no-underline"
    >
      {kind}
    </abbr>
  );
}
