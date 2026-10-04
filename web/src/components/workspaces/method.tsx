"use client";

import { useRef } from "react";
import { gsap } from "gsap";
import { useGSAP } from "@gsap/react";

import { Workspace } from "@/components/wm/workspace";

const STAGES = [
  { name: "Collect", model: "BSE · RBI · SEBI · NCLT", base: "robots.txt, rate-limited" },
  { name: "Prepare", model: "PyMuPDF + OCR", base: "MinHash dedup, LexRank prune" },
  { name: "Entities", model: "DeBERTa-v3 NER", base: "vs CRF + gazetteer" },
  { name: "Sentiment", model: "FinBERT, entity-marked", base: "vs TF-IDF + LR" },
  { name: "Events", model: "Qwen 2.5 7B", base: "vs rules" },
  { name: "Summary", model: "Llama 3.1 8B", base: "vs Lead-3" },
  { name: "Verify", model: "BM25 + bge-m3 → NLI", base: "entailed / contradicted" },
];

/** The pipeline as a vertical rail: one row per stage, a document travelling down it. */
function PipelineDiagram() {
  const ref = useRef<HTMLOListElement>(null);
  useGSAP(
    () => {
      const mm = gsap.matchMedia();
      mm.add("(prefers-reduced-motion: no-preference)", () => {
        gsap.from(".pd-row", { opacity: 0, x: -10, duration: 0.5, stagger: 0.06, ease: "expo.out" });
        const rows = gsap.utils.toArray<HTMLElement>(".pd-row");
        const tl = gsap.timeline({ repeat: -1, repeatDelay: 0.8, delay: 0.8 });
        rows.forEach((row) => {
          tl.to(row, { backgroundColor: "var(--accent-weak)", duration: 0.25 }).to(row, { backgroundColor: "rgba(0,0,0,0)", duration: 0.5 }, "+=0.35");
        });
      });
      return () => mm.revert();
    },
    { scope: ref },
  );
  return (
    <ol ref={ref} aria-label="FinPulse pipeline, top to bottom" className="relative">
      <span className="absolute top-4 bottom-4 left-[19px] w-px bg-line-strong" aria-hidden="true" />
      {STAGES.map((s, i) => (
        <li key={s.name} className="pd-row relative grid grid-cols-[40px_minmax(0,9rem)_minmax(0,1fr)] items-baseline gap-x-3 py-2.5 pr-2">
          <span className="relative z-[1] mx-auto flex size-6 items-center justify-center border border-line-strong bg-surface font-mono text-2xs text-ink-2">
            {i + 1}
          </span>
          <span className={i === 3 ? "text-md font-semibold text-accent-ink" : "text-md font-semibold text-ink"}>{s.name}</span>
          <span className="min-w-0">
            <span className="block font-mono text-xs text-ink">{s.model}</span>
            <span className="block font-mono text-2xs text-ink-3">{s.base}</span>
          </span>
        </li>
      ))}
      <li className="mt-2 ml-[52px] border border-dashed border-line-strong px-3 py-2 font-mono text-2xs leading-relaxed text-ink-2">
        PostgreSQL + pgvector · documents, sentences, spans, events, claims, runs · gold and silver labels kept apart. Everything
        runs locally on one GPU; models take turns, and every run records model, prompt version and latency.
      </li>
    </ol>
  );
}

const RQ = [
  ["RQ1", "Can a FinBERT-family model give the right sentiment to each company when one article names several?"],
  ["RQ2", "Which event schema captures Indian regulatory and corporate events in unstructured filings?"],
  ["RQ3", "Can every generated summary claim be mapped to a supporting source sentence?"],
  ["RQ4", "How well do Western-trained financial models transfer to Indian disclosure language?"],
];

const DATA: [string, string, string][] = [
  ["FinEntity", "979 paragraphs, 2,131 entity spans", "entity spans + sentiment benchmark"],
  ["SEntFiN 1.0", "10,753 Indian headlines", "Indian entity sentiment, alias list"],
  ["Financial PhraseBank", "4,845 sentences", "sentence sentiment warm-up"],
  ["FiQA 2018 task 1", "~1,173 items", "aspect sentiment (thresholded)"],
  ["EDT", "9,721 articles, 11 event types", "event taxonomy and evaluation"],
  ["ECTSum", "2,425 transcript–summary pairs", "long-document summary evaluation"],
  ["FinPulse corpus", "BSE, RBI, SEBI, NCLT disclosures", "new: gold and silver labels, IEEE DataPort"],
];

const TEAM: [string, string, string][] = [
  ["Sania S", "CB.SC.U4CSE24046", "Data and pipeline: corpus collection, preprocessing, pruning, integration"],
  ["Hasini K", "CB.SC.U4CSE24123", "Events and generation: event schema, extraction, grounded summaries, verification"],
  ["Shruhath Reddy", "CB.SC.U4CSE24124", "Models and evaluation: entity-level FinBERT, baselines, metrics"],
];

export function MethodWorkspace() {
  return (
    <Workspace
      tiles={[
        {
          id: "diagram",
          cls: "diagram",
          title: "pipeline",
          mobileMinH: 240,
          node: (
            <div className="flex flex-col gap-4">
              <PipelineDiagram />
              <p className="max-w-[80ch] text-sm leading-relaxed text-ink-2">
                Each stage has one job, an inspectable input and a constrained output, and each neural stage is compared
                against a classical baseline. Long filings are pruned before generation, and every summary sentence is
                checked against a retrieved source sentence by an NLI model before it is shown.
              </p>
            </div>
          ),
        },
        {
          id: "rq",
          cls: "doc",
          title: "research questions",
          weight: 1.1,
          node: (
            <ol className="space-y-3">
              {RQ.map(([k, q]) => (
                <li key={k} className="grid grid-cols-[40px_1fr] gap-2 text-sm">
                  <span className="font-mono text-xs font-semibold text-accent-ink">{k}</span>
                  <span className="leading-snug text-ink">{q}</span>
                </li>
              ))}
            </ol>
          ),
        },
        {
          id: "datasets",
          cls: "table",
          title: "datasets",
          weight: 1.4,
          flush: true,
          node: (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line font-mono text-2xs text-ink-3">
                  <th scope="col" className="px-3 py-1.5 text-left font-medium">dataset</th>
                  <th scope="col" className="px-3 py-1.5 text-left font-medium">size</th>
                  <th scope="col" className="px-3 py-1.5 text-left font-medium">role</th>
                </tr>
              </thead>
              <tbody>
                {DATA.map(([n, s, r]) => (
                  <tr key={n} className="border-b border-line last:border-0">
                    <th scope="row" className="px-3 py-1.5 text-left font-semibold text-ink">{n}</th>
                    <td className="px-3 py-1.5 font-mono text-xs text-ink-2">{s}</td>
                    <td className="px-3 py-1.5 text-ink-2">{r}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ),
        },
        {
          id: "ethics",
          cls: "doc",
          title: "sources and ethics",
          weight: 1.1,
          node: (
            <ul className="list-disc space-y-1.5 pl-4 text-sm leading-snug text-ink-2 marker:text-ink-3">
              <li>Only public disclosures from exchanges and regulators; news is linked by URL and offsets, not republished.</li>
              <li>robots.txt is respected and every source is rate-limited to one request per second.</li>
              <li>Human gold labels and machine silver labels never share a file, row or export.</li>
              <li>FinPulse describes what documents say. It does not give investment advice.</li>
            </ul>
          ),
        },
        {
          id: "team",
          cls: "who",
          title: "team 6 · 23CSE471 natural language processing",
          weight: 1,
          node: (
            <div className="space-y-3">
              <ul className="space-y-2">
                {TEAM.map(([n, r, role]) => (
                  <li key={n} className="text-sm">
                    <span className="font-semibold text-ink">{n}</span>
                    <span className="ml-2 font-mono text-2xs text-ink-3">{r}</span>
                    <p className="text-ink-2">{role}</p>
                  </li>
                ))}
              </ul>
              <p className="border-t border-line pt-2 font-mono text-2xs text-ink-3">
                guide: Dr. T. Senthil Kumar, CSE · Amrita Vishwa Vidyapeetham
              </p>
            </div>
          ),
        },
      ]}
    />
  );
}
