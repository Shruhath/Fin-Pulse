import type { Metadata } from "next";
import Link from "next/link";

import { PageHeader } from "@/components/app/page-header";

export const metadata: Metadata = { title: "Method" };

const STAGES = [
  { name: "Collect", model: "SEBI orders, NCLT orders via IBBI, the RBI press-release feed", base: "One request per second; stops if a site blocks it." },
  { name: "Prepare", model: "PyMuPDF text layer, Tesseract for scanned pages", base: "Near-duplicates removed; long filings pruned before generation." },
  { name: "Companies", model: "Name matching against a list of listed companies, plus the parties named in an order's title", base: "DeBERTa-v3 and a CRF were measured as alternatives." },
  { name: "Sentiment", model: "FinBERT, entity-marked and calibrated", base: "Compared with TF-IDF and logistic regression." },
  { name: "Events", model: "Qwen 2.5 7B, output checked against a schema", base: "Compared with a rules baseline." },
  { name: "Summary", model: "Llama 3.1 8B, every claim cites a sentence", base: "Compared with taking the first three sentences." },
  { name: "Verify", model: "BM25 and bge-base retrieval, then a DeBERTa NLI model", base: "Each claim is marked supported, contradicted or not verified." },
];

const RQ = [
  "Can a FinBERT-family model give the right sentiment to each company when one article names several?",
  "Which event schema captures Indian regulatory and corporate events in unstructured filings?",
  "Can every generated summary claim be mapped to a supporting source sentence?",
  "How well do Western-trained financial models transfer to Indian disclosure language?",
];

const DATA: [string, string, string][] = [
  ["FinEntity", "979 paragraphs, 2,131 entity spans", "Entity spans and sentiment benchmark"],
  ["SEntFiN 1.0", "10,753 Indian headlines", "Indian entity sentiment and an alias list"],
  ["EDT", "9,721 articles, 11 event types", "Starting point for the event taxonomy; not trained on"],
  ["ECTSum", "2,425 transcript and summary pairs", "Summary evaluation on a 40-transcript sample"],
  ["FinPulse corpus", "SEBI, NCLT and RBI disclosures", "New: machine labels now, human labels once annotated"],
];

const TEAM: [string, string, string][] = [
  ["Sania S", "CB.SC.U4CSE24046", "Data and pipeline: corpus collection, preprocessing, pruning, integration"],
  ["Hasini K", "CB.SC.U4CSE24123", "Events and generation: event schema, extraction, grounded summaries, verification"],
  ["Shruhath Reddy", "CB.SC.U4CSE24124", "Models and evaluation: entity-level FinBERT, baselines, metrics"],
];

const h2 = "mb-4 text-xl font-semibold text-ink";

export default function MethodPage() {
  return (
    <div className="max-w-3xl">
      <PageHeader
        title="How FinPulse works"
        description="Seven stages, each with one job, an inspectable input and a constrained output. Every neural stage is compared against a simpler baseline."
      />

      <section aria-labelledby="pipeline" className="mb-14">
        <h2 id="pipeline" className="sr-only">
          The pipeline
        </h2>
        <ol className="relative">
          <span className="absolute top-4 bottom-4 left-[15px] w-0.5 rounded-full bg-line" aria-hidden="true" />
          {STAGES.map((s, i) => (
            <li key={s.name} className="relative grid grid-cols-[2rem_1fr] gap-x-5 pb-7 last:pb-0">
              <span className="relative z-[1] flex size-8 items-center justify-center rounded-full bg-brand text-sm font-bold text-white">{i + 1}</span>
              <div>
                <p className="text-md font-semibold text-ink">{s.name}</p>
                <p className="mt-0.5 text-base text-ink">{s.model}</p>
                <p className="text-sm text-ink-3">{s.base}</p>
              </div>
            </li>
          ))}
        </ol>
        <p className="mt-8 rounded-2xl bg-surface-2 px-5 py-4 text-base leading-7 text-ink-2">
          Everything is stored in PostgreSQL with pgvector: documents, sentences, mentions, events, claims and every run with its model, prompt version
          and latency. Human labels and machine labels are kept apart. Every model runs on one local GPU and takes its turn; nothing is sent to a hosted API.
        </p>
      </section>

      <section className="mb-14">
        <h2 className={h2}>What we set out to answer</h2>
        <ol className="space-y-3">
          {RQ.map((q, i) => (
            <li key={q} className="grid grid-cols-[2.75rem_1fr] items-baseline gap-x-2 text-base leading-7">
              <span className="text-sm font-bold text-brand-ink">RQ{i + 1}</span>
              <span className="text-ink">{q}</span>
            </li>
          ))}
        </ol>
      </section>

      <section className="mb-14">
        <h2 className={h2}>Data</h2>
        <div className="overflow-x-auto rounded-2xl border border-line bg-surface shadow-1">
          <table className="w-full text-base">
            <thead>
              <tr className="border-b border-line bg-surface-2/60 text-sm text-ink-3">
                <th scope="col" className="px-4 py-3 text-left font-medium">
                  Dataset
                </th>
                <th scope="col" className="px-4 py-3 text-left font-medium">
                  Size
                </th>
                <th scope="col" className="px-4 py-3 text-left font-medium">
                  What it is for
                </th>
              </tr>
            </thead>
            <tbody>
              {DATA.map(([n, s, r]) => (
                <tr key={n} className="border-b border-line align-top last:border-0">
                  <th scope="row" className="px-4 py-3 text-left font-semibold whitespace-nowrap text-ink">
                    {n}
                  </th>
                  <td className="px-4 py-3 text-ink-2">{s}</td>
                  <td className="px-4 py-3 text-ink-2">{r}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="mb-14">
        <h2 className={h2}>Sources and ethics</h2>
        <ul className="list-disc space-y-2 pl-5 text-base leading-7 text-ink-2 marker:text-ink-3">
          <li>Only public disclosures from exchanges and regulators. News is linked by address and offsets, not republished.</li>
          <li>robots.txt is respected and every source is limited to one request per second.</li>
          <li>Human labels and machine labels never share a file, a row or an export.</li>
          <li>The published dataset carries offsets, labels and hashes, not order text, until the publishers have given permission.</li>
          <li>FinPulse describes what documents say. It does not give investment advice.</li>
        </ul>
        <p className="mt-4 text-base text-ink-2">
          For the measured results and where they fall short, see{" "}
          <Link href="/evaluation" className="font-medium text-brand-ink hover:underline">
            Evaluation
          </Link>
          .
        </p>
      </section>

      <section>
        <h2 className={h2}>Team 6 · 23CSE471 Natural Language Processing</h2>
        <ul className="space-y-4">
          {TEAM.map(([n, r, role]) => (
            <li key={n}>
              <p className="text-base">
                <span className="font-semibold text-ink">{n}</span>
                <span className="num ml-2 text-sm text-ink-3">{r}</span>
              </p>
              <p className="text-base text-ink-2">{role}</p>
            </li>
          ))}
        </ul>
        <p className="mt-5 border-t border-line pt-4 text-sm text-ink-3">Guide: Dr. T. Senthil Kumar, CSE · Amrita Vishwa Vidyapeetham</p>
      </section>
    </div>
  );
}
