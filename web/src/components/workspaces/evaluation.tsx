"use client";

import { ConfusionMatrix, Reliability, TransferPlot } from "@/components/charts/eval-charts";
import { Empty } from "@/components/ui/states";
import { Workspace } from "@/components/wm/workspace";
import type { EvalReport, MetricRow } from "@/lib/api/types";
import { fmtDayLong, fmtInt } from "@/lib/format";

const TASK: Record<MetricRow["task"], string> = {
  ner: "Entity recognition and linking",
  sentiment: "Entity-level sentiment",
  events: "Event extraction",
  summaries: "Grounded summaries",
  qa: "Question answering (silver questions generated from the corpus)",
};

const METRIC_LABEL: Record<string, string> = {
  macroF1: "macro-F1",
  weightedF1: "weighted-F1",
  ece: "ECE",
  ece_before: "ECE before",
  temperature: "temperature",
  accuracy: "accuracy",
  n: "n",
  spanF1: "span F1",
  spanPrecision: "span precision",
  spanRecall: "span recall",
  goldSpans: "gold spans",
  rouge1: "ROUGE-1",
  rouge2: "ROUGE-2",
  contradicted: "contradicted",
  skipped: "skipped",
  hitAt8Entity: "hit@8, company named",
  hitAt8Amount: "hit@8, amount only",
  answered: "answered",
  claimsEntailed: "claims supported",
  claimsContradicted: "claims contradicted",
  abstainAbsent: "abstains, absent company",
  abstainOfftopic: "abstains, off topic",
  medianSeconds: "median seconds",
  linkAcc: "link acc.",
  typeF1: "type F1",
  argF1: "argument F1",
  validity: "schema valid",
  rougeL: "ROUGE-L",
  bertScore: "BERTScore",
  attribution: "attribution",
  unsupported: "unsupported",
};

const COUNTS = new Set(["n", "goldSpans", "skipped"]);
const THREE_PLACES = new Set(["ece", "ece_before"]);
const formatMetric = (key: string, v: number) => (COUNTS.has(key) ? fmtInt(v) : v.toFixed(THREE_PLACES.has(key) ? 3 : 2));

export function EvaluationWorkspace({ report, preview }: { report: EvalReport; preview: boolean }) {
  const measured = report.rows.length > 0;
  const sentiment = report.rows.filter((r) => r.task === "sentiment");
  const stamp = report.generatedAt ? `run ${fmtDayLong(report.generatedAt)}` : "not run yet";
  const tag = preview ? <span className="font-mono text-warn">synthetic</span> : <span className="font-mono">{stamp}</span>;
  return (
    <Workspace
      tiles={[
        {
          id: "transfer",
          cls: "chart",
          title: "entity sentiment · public vs Indian data",
          flush: true,
          mobileMinH: 320,
          meta: tag,
          node: sentiment.length ? <TransferPlot rows={sentiment} /> : <Empty>Sentiment has not been evaluated yet. Results appear here once the harness runs.</Empty>,
        },
        {
          id: "confusion",
          cls: "matrix",
          title: report.confusion ? `confusion · ${report.confusion.dataset.toLowerCase()}` : "confusion",
          weight: 1.25,
          mobileMinH: 260,
          meta: tag,
          node: report.confusion ? <ConfusionMatrix data={report.confusion} /> : <Empty>No confusion matrix yet.</Empty>,
        },
        {
          id: "calibration",
          cls: "chart",
          title: "calibration",
          weight: 1.25,
          flush: true,
          mobileMinH: 260,
          meta: tag,
          node: report.reliability ? <Reliability {...report.reliability} /> : <Empty>Calibration has not been measured yet.</Empty>,
        },
        {
          id: "metrics",
          cls: "table",
          title: "all metrics",
          weight: 1.6,
          flush: true,
          meta: tag,
          node: measured ? <MetricsTable rows={report.rows} agreement={report.agreement} /> : <Empty>Nothing measured yet.</Empty>,
        },
      ]}
    />
  );
}

function MetricsTable({ rows, agreement }: { rows: MetricRow[]; agreement: EvalReport["agreement"] }) {
  const tasks = [...new Set(rows.map((r) => r.task))];
  return (
    <div className="divide-y divide-line">
      {tasks.map((t) => {
        const rs = rows.filter((r) => r.task === t);
        const keys = [...new Set(rs.flatMap((r) => Object.keys(r.metrics)))];
        return (
          <section key={t}>
            <h3 className="bg-surface-2 px-3 py-1.5 font-mono text-2xs font-semibold text-ink-2">{TASK[t].toLowerCase()}</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-line font-mono text-2xs text-ink-3">
                    <th scope="col" className="px-3 py-1.5 text-left font-medium">model</th>
                    <th scope="col" className="px-3 py-1.5 text-left font-medium">dataset</th>
                    {keys.map((k) => (
                      <th key={k} scope="col" className="px-3 py-1.5 text-right font-medium">
                        {METRIC_LABEL[k] ?? k}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rs.map((r, i) => (
                    <tr key={i} className="border-b border-line last:border-0">
                      <th scope="row" className={r.baseline ? "px-3 py-1.5 text-left font-normal text-ink-2" : "px-3 py-1.5 text-left font-semibold text-ink"}>
                        {r.model}
                        {r.baseline && <span className="ml-1.5 font-mono text-2xs text-ink-3">baseline</span>}
                      </th>
                      <td className="px-3 py-1.5 text-ink-2">
                        {r.dataset}
                        {r.indian && <span className="ml-1.5 font-mono text-2xs text-accent-ink">IN</span>}
                      </td>
                      {keys.map((k) => (
                        <td key={k} className="px-3 py-1.5 text-right font-mono text-xs text-ink">
                          {r.metrics[k] === undefined ? "—" : formatMetric(k, r.metrics[k])}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        );
      })}
      {agreement.length > 0 && (
        <section>
          <h3 className="bg-surface-2 px-3 py-1.5 font-mono text-2xs font-semibold text-ink-2">inter-annotator agreement (cohen&apos;s κ)</h3>
          <dl className="grid grid-cols-[1fr_auto_auto] gap-x-6 gap-y-1 px-3 py-2 text-sm">
            {agreement.map((a) => (
              <div key={a.task} className="contents">
                <dt className="text-ink-2">{a.task}</dt>
                <dd className="text-right font-mono text-xs text-ink">κ {a.kappa.toFixed(2)}</dd>
                <dd className="text-right font-mono text-2xs text-ink-3">{a.items} docs</dd>
              </div>
            ))}
          </dl>
        </section>
      )}
    </div>
  );
}
