import type { EvalReport } from "@/lib/api/types";

/** Model names carry a build hash for the record (finbert-entity@c4abaaad); a reader does not need it. */
const plainName = (name: string) => name.replace(/\s*\([^)]*@[0-9a-f]+\)\s*$/i, "");

/** Pairs of (model, baseline) macro-F1 per sentiment dataset, taken from the evaluation harness. */
export function sentimentPairs(report: EvalReport) {
  const out: { dataset: string; model: { name: string; v: number }; baseline: { name: string; v: number } }[] = [];
  const rows = report.rows.filter((r) => r.task === "sentiment" && typeof r.metrics.macroF1 === "number");
  for (const dataset of [...new Set(rows.map((r) => r.dataset))]) {
    const here = rows.filter((r) => r.dataset === dataset);
    const best = here.filter((r) => !r.baseline).sort((a, b) => b.metrics.macroF1 - a.metrics.macroF1)[0];
    const base = here.filter((r) => r.baseline).sort((a, b) => b.metrics.macroF1 - a.metrics.macroF1)[0];
    if (best && base) out.push({ dataset, model: { name: plainName(best.model), v: best.metrics.macroF1 }, baseline: { name: plainName(base.model), v: base.metrics.macroF1 } });
  }
  return out;
}

function Bar({ name, v, tone }: { name: string; v: number; tone: "model" | "base" }) {
  return (
    <div className="grid grid-cols-[minmax(0,1fr)_3rem] items-center gap-x-4 gap-y-1 sm:grid-cols-[minmax(0,17rem)_1fr_3rem]">
      <span className={tone === "model" ? "text-sm leading-5 font-semibold text-ink" : "text-sm leading-5 text-ink-3"}>{name}</span>
      <span className="order-last col-span-2 h-2.5 overflow-hidden rounded-full bg-surface-3 sm:order-none sm:col-span-1" aria-hidden="true">
        <span className={tone === "model" ? "block h-full rounded-full bg-brand" : "block h-full rounded-full bg-ink-3/60"} style={{ width: `${Math.round(v * 100)}%` }} />
      </span>
      <span className="num text-right text-sm font-semibold text-ink">{v.toFixed(2)}</span>
    </div>
  );
}

export function SentimentResults({ report }: { report: EvalReport }) {
  const pairs = sentimentPairs(report);
  if (pairs.length === 0) return null;
  return (
    <div className="space-y-8">
      {pairs.map((p) => (
        <div key={p.dataset}>
          <h3 className="mb-3 text-base font-semibold text-ink">{p.dataset}</h3>
          <div className="space-y-2.5">
            <Bar name={p.model.name} v={p.model.v} tone="model" />
            <Bar name={p.baseline.name} v={p.baseline.v} tone="base" />
          </div>
        </div>
      ))}
    </div>
  );
}
