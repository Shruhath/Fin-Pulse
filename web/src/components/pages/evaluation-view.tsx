"use client";

import { useState } from "react";
import clsx from "clsx";

import { PageHeader } from "@/components/app/page-header";
import { TabBar, TabPanel, TabRoot } from "@/components/app/tab-bar";
import { ConfusionMatrix, Reliability, TransferPlot } from "@/components/charts/eval-charts";
import { Empty } from "@/components/ui/states";
import type { EvalReport, MetricRow } from "@/lib/api/types";
import { fmtDayLong, fmtInt } from "@/lib/format";

type Task = MetricRow["task"];

const TASKS: { task: Task; tab: string; title: string }[] = [
  { task: "sentiment", tab: "Sentiment", title: "Entity-level sentiment" },
  { task: "ner", tab: "Companies", title: "Company recognition and linking" },
  { task: "events", tab: "Events", title: "Event extraction" },
  { task: "summaries", tab: "Summaries", title: "Grounded summaries" },
  { task: "qa", tab: "Questions", title: "Question answering (silver questions generated from the corpus)" },
];

const METRIC_LABEL: Record<string, string> = {
  macroF1: "Macro-F1",
  weightedF1: "Weighted F1",
  ece: "ECE",
  ece_before: "ECE before",
  temperature: "Temperature",
  accuracy: "Accuracy",
  n: "n",
  spanF1: "Span F1",
  spanPrecision: "Span precision",
  spanRecall: "Span recall",
  goldSpans: "Gold spans",
  rouge1: "ROUGE-1",
  rouge2: "ROUGE-2",
  contradicted: "Contradicted",
  skipped: "Skipped",
  hitAt8Entity: "Hit@8, company named",
  hitAt8Amount: "Hit@8, amount only",
  answered: "Answered",
  claimsEntailed: "Claims supported",
  claimsContradicted: "Claims contradicted",
  abstainAbsent: "Abstains, absent company",
  abstainOfftopic: "Abstains, off topic",
  entailedEntity: "Supported, company named",
  entailedAmount: "Supported, amount only",
  linkAcc: "Link accuracy",
  typeF1: "Type F1",
  argF1: "Argument F1",
  validity: "Schema valid",
  rougeL: "ROUGE-L",
  bertScore: "BERTScore",
  attribution: "Attribution",
  unsupported: "Unsupported",
  recallDifferent: "Finds a difference",
  recallSame: "Confirms a match",
  schemaValid: "Passes the schema",
  agreeRecall: "Rule events it also finds",
  agreePrecision: "Its events the rules agree with",
  amountMatch: "Same amount as rules",
  documents: "Documents",
  wer: "Word error rate",
};

const COUNTS = new Set(["n", "goldSpans", "skipped", "documents"]);
const THREE_PLACES = new Set(["ece", "ece_before", "wer"]);
const formatMetric = (key: string, v: number) => (COUNTS.has(key) ? fmtInt(v) : v.toFixed(THREE_PLACES.has(key) ? 3 : 2));

export function EvaluationView({ report, preview }: { report: EvalReport; preview: boolean }) {
  const have = TASKS.filter((t) => t.task === "sentiment" || report.rows.some((r) => r.task === t.task));
  const [tab, setTab] = useState(have[0].task);
  const stamp = preview ? "Synthetic figures" : report.generatedAt ? `Run on ${fmtDayLong(report.generatedAt)}` : "Not run yet";

  return (
    <>
      <PageHeader
        title="Evaluation"
        description="How each stage scored against the baseline it replaces, on public benchmarks and on Indian data. Every figure comes from the evaluation harness."
        actions={<span className="rounded-full bg-surface-3 px-3.5 py-1.5 text-sm font-medium text-ink-2">{stamp}</span>}
      />
      <TabRoot value={tab} onValueChange={(v) => setTab(v as Task)}>
        <TabBar active={tab} items={have.map((t) => ({ value: t.task, label: t.tab }))} />
        {have.map((t) => {
          const rows = report.rows.filter((r) => r.task === t.task);
          return (
            <TabPanel key={t.task} value={t.task} className="space-y-8">
              {t.task === "sentiment" && (
                <>
                  <Panel title="Public benchmark against Indian data" note="Each row is a model; the line between the two marks is how much it loses when it moves to Indian text.">
                    <div className="h-[340px]">
                      {rows.length ? <TransferPlot rows={rows} /> : <Empty>Sentiment has not been evaluated yet. Results appear here once the harness runs.</Empty>}
                    </div>
                  </Panel>
                  <div className="grid gap-8 lg:grid-cols-2">
                    <Panel title={report.confusion ? `Where it goes wrong (${report.confusion.dataset})` : "Where it goes wrong"}>
                      <div className="h-[300px]">{report.confusion ? <ConfusionMatrix data={report.confusion} /> : <Empty>No confusion matrix yet.</Empty>}</div>
                    </Panel>
                    <Panel title="Calibration" note="A model that says 80% should be right about 80% of the time.">
                      <div className="h-[300px]">{report.reliability ? <Reliability {...report.reliability} /> : <Empty>Calibration has not been measured yet.</Empty>}</div>
                    </Panel>
                  </div>
                </>
              )}
              <section>
                <h2 className="mb-3 text-lg font-semibold text-ink">{t.title}</h2>
                {rows.length ? <MetricsTable rows={rows} /> : <Empty>Nothing measured yet for this stage.</Empty>}
              </section>
              {t.task === "sentiment" && report.agreement.length > 0 && (
                <section>
                  <h2 className="mb-3 text-lg font-semibold text-ink">Agreement between annotators</h2>
                  <dl className="grid max-w-md grid-cols-[1fr_auto_auto] gap-x-6 gap-y-2 rounded-2xl border border-line bg-surface p-5 text-base shadow-1">
                    {report.agreement.map((a) => (
                      <div key={a.task} className="contents">
                        <dt className="text-ink-2">{a.task}</dt>
                        <dd className="num text-right font-semibold text-ink">κ {a.kappa.toFixed(2)}</dd>
                        <dd className="num text-right text-sm text-ink-3">{a.items} docs</dd>
                      </div>
                    ))}
                  </dl>
                </section>
              )}
            </TabPanel>
          );
        })}
      </TabRoot>
      <EveryModel rows={report.rows} />
    </>
  );
}

interface ModelLine {
  name: string;
  job: string;
  task: Task;
  pick: (r: MetricRow) => boolean;
  metric: string;
  lowerIsBetter?: boolean;
  note?: string;
}

const MODELS: ModelLine[] = [
  { name: "FinBERT, entity-marked, fine-tuned", job: "Sentiment for each company", task: "sentiment", pick: (r) => /Entity-marked FinBERT/.test(r.model) && r.dataset.startsWith("SEntFiN"), metric: "macroF1" },
  { name: "DeBERTa-v3 token classifier", job: "Finds company names", task: "ner", pick: (r) => /DeBERTa-v3 token/.test(r.model) && r.dataset.startsWith("SEntFiN"), metric: "spanF1" },
  { name: "DeBERTa-v3 NLI", job: "Checks each claim against its source sentence", task: "summaries", pick: (r) => /NLI \(claim checker\)/.test(r.model), metric: "macroF1", note: "never misses a difference, rarely confirms a match" },
  { name: "bge-base-en-v1.5 embedder, with keyword search", job: "Finds sentences by meaning", task: "qa", pick: (r) => !r.baseline && /llama/.test(r.model), metric: "hitAt8Entity", note: "measured through Ask" },
  { name: "Qwen 2.5 7B", job: "Extracts events as structured records", task: "events", pick: (r) => /qwen/.test(r.model), metric: "schemaValid", note: "agrees with the rule baseline; no human labels yet" },
  { name: "Llama 3.1 8B", job: "Writes summaries and answers, each claim cited", task: "summaries", pick: (r) => /^llama/.test(r.model), metric: "rouge1", note: "ECTSum sample, with the NLI check" },
  { name: "Whisper base.en", job: "Turns a spoken question into text", task: "qa", pick: (r) => /Whisper base\.en with/.test(r.model), metric: "wer", lowerIsBetter: true, note: "synthetic speech only" },
];

/** One line per model in the system with the figure that measures it, so no model is left out of the report. */
function EveryModel({ rows }: { rows: MetricRow[] }) {
  return (
    <section className="mt-12" aria-labelledby="every-model">
      <h2 id="every-model" className="text-lg font-semibold text-ink">
        Every model
      </h2>
      <p className="mt-1 mb-3 max-w-[70ch] text-sm text-ink-3">
        Each model in the pipeline and how it was measured. The baseline is the best simpler method on the same data.
        A dash means that measure has not been run.
      </p>
      <div className="overflow-x-auto rounded-2xl border border-line bg-surface shadow-1">
        <table className="w-full text-base">
          <thead>
            <tr className="border-b border-line bg-surface-2/60 text-sm text-ink-3">
              {["Model", "What it does", "Measure", "Value", "Best baseline", "Data"].map((h, i) => (
                <th key={h} scope="col" className={clsx("px-4 py-3 font-medium whitespace-nowrap", i === 3 || i === 4 ? "text-right" : "text-left")}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {MODELS.map((m) => {
              const row = rows.find((r) => r.task === m.task && m.pick(r) && r.metrics[m.metric] !== undefined);
              const value = row?.metrics[m.metric];
              const peers = row ? rows.filter((r) => r.task === m.task && r.baseline && r.dataset === row.dataset && r.metrics[m.metric] !== undefined).map((r) => r.metrics[m.metric]) : [];
              const baseline = peers.length ? (m.lowerIsBetter ? Math.min(...peers) : Math.max(...peers)) : undefined;
              return (
                <tr key={m.name} className="border-b border-line last:border-0 align-top">
                  <th scope="row" className="px-4 py-3 text-left font-semibold text-ink">
                    {m.name}
                  </th>
                  <td className="px-4 py-3 text-ink-2">
                    {m.job}
                    {m.note && <span className="mt-0.5 block text-sm text-ink-3">{m.note}</span>}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-ink-2">
                    {METRIC_LABEL[m.metric] ?? m.metric}
                    <span className="ml-1 text-xs text-ink-3">{m.lowerIsBetter ? "lower is better" : "higher is better"}</span>
                  </td>
                  <td className="num px-4 py-3 text-right font-semibold text-ink">{value === undefined ? "–" : formatMetric(m.metric, value)}</td>
                  <td className="num px-4 py-3 text-right text-ink-2">{baseline === undefined ? "–" : formatMetric(m.metric, baseline)}</td>
                  <td className="px-4 py-3 text-sm text-ink-3">{row?.dataset ?? "Not measured yet"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="mt-3 max-w-[70ch] text-sm text-ink-3">
        Explanations: the sentiment of a company in a filing can be opened with <strong className="font-semibold">Why this score</strong>,
        which shows how much each word pushed it (Integrated Gradients), with the error of the approximation shown next to it.
      </p>
    </section>
  );
}

function Panel({ title, note, children }: { title: string; note?: string; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl border border-line bg-surface p-5 shadow-1">
      <h2 className="text-lg font-semibold text-ink">{title}</h2>
      {note && <p className="mt-0.5 mb-3 text-sm text-ink-3">{note}</p>}
      <div className={note ? "" : "mt-3"}>{children}</div>
    </section>
  );
}

function MetricsTable({ rows }: { rows: MetricRow[] }) {
  const keys = [...new Set(rows.flatMap((r) => Object.keys(r.metrics)))];
  return (
    <div className="overflow-x-auto rounded-2xl border border-line bg-surface shadow-1">
      <table className="w-full text-base">
        <thead>
          <tr className="border-b border-line bg-surface-2/60 text-sm text-ink-3">
            <th scope="col" className="px-4 py-3 text-left font-medium">
              Model
            </th>
            <th scope="col" className="px-4 py-3 text-left font-medium">
              Dataset
            </th>
            {keys.map((k) => (
              <th key={k} scope="col" className="px-4 py-3 text-right font-medium whitespace-nowrap">
                {METRIC_LABEL[k] ?? k}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-b border-line last:border-0">
              <th scope="row" className={r.baseline ? "px-4 py-3 text-left font-normal text-ink-2" : "px-4 py-3 text-left font-semibold text-ink"}>
                {r.model}
                {r.baseline && <span className="ml-2 rounded-full bg-surface-3 px-2 py-0.5 text-xs font-medium text-ink-3">Baseline</span>}
              </th>
              <td className="px-4 py-3 text-ink-2">
                {r.dataset}
                {r.indian && <span className="ml-2 rounded-full bg-brand-weak px-2 py-0.5 text-xs font-semibold text-brand-ink">Indian</span>}
              </td>
              {keys.map((k) => (
                <td key={k} className="num px-4 py-3 text-right text-ink">
                  {r.metrics[k] === undefined ? "–" : formatMetric(k, r.metrics[k])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
