import { OverviewBoard } from "@/components/overview/board";
import { OfflineState } from "@/components/ui/states";
import { getOverview, parseWindow } from "@/lib/api/client";
import type { Overview } from "@/lib/api/types";
import { fmtInt, fmtScore } from "@/lib/format";

const WINDOW_LABEL = { "7d": "7 days", "30d": "30 days", "90d": "90 days" } as const;

export default async function OverviewPage(props: PageProps<"/">) {
  const { w } = await props.searchParams;
  const window = parseWindow(w);
  const res = await getOverview(window);
  if (res.state === "offline") return <OfflineState message={res.message} />;
  const data = res.data;

  return (
    <div className="mx-auto max-w-[1600px] px-4 py-6 sm:px-6 lg:py-8">
      <header className="mb-6 flex flex-wrap items-end gap-x-8 gap-y-3">
        <div className="min-w-0 flex-1">
          <h1 className="text-xl font-semibold text-ink">Market overview</h1>
          <p className="mt-1 max-w-[72ch] text-base text-ink-2">{summarise(data, WINDOW_LABEL[window])}</p>
        </div>
        <SourceMix sources={data.sources} />
      </header>
      <OverviewBoard data={data} />
    </div>
  );
}

function summarise(d: Overview, label: string) {
  if (d.market.length === 0) return `Nothing has been scored in the last ${label}.`;
  const mean = d.market.reduce((a, p) => a + p.mean, 0) / d.market.length;
  const spread = d.market.reduce((a, p) => a + p.std, 0) / d.market.length;
  const pos = d.entities.filter((e) => e.sentiment === "positive").length;
  const neg = d.entities.filter((e) => e.sentiment === "negative").length;
  return `Over the last ${label}, company sentiment averaged ${fmtScore(mean)} with a typical spread of ±${spread.toFixed(2)}. ${pos} of ${d.entities.length} companies lean positive and ${neg} lean negative, with ${d.events.length} events extracted.`;
}

function SourceMix({ sources }: { sources: Overview["sources"] }) {
  const total = sources.reduce((a, s) => a + s.documents, 0);
  return (
    <dl className="flex flex-wrap gap-x-5 gap-y-1 text-xs">
      {sources.map((s) => (
        <div key={s.kind} className="flex items-baseline gap-1.5">
          <dt className="font-mono text-ink-3">{s.kind}</dt>
          <dd className="num font-semibold text-ink-2">{fmtInt(s.documents)}</dd>
        </div>
      ))}
      <div className="flex items-baseline gap-1.5 border-l border-line pl-5">
        <dt className="text-ink-3">Total</dt>
        <dd className="num font-semibold text-ink">{fmtInt(total)}</dd>
      </div>
    </dl>
  );
}
