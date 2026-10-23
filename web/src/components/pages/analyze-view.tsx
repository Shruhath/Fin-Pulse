"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import * as Tabs from "@radix-ui/react-tabs";
import { ChevronDown, FileUp, Play, RotateCcw } from "lucide-react";
import clsx from "clsx";

import { useApp } from "@/components/app/app-context";
import { PageHeader } from "@/components/app/page-header";
import { StageLine, type Stage } from "@/components/app/stage-line";
import { TabBar } from "@/components/app/tab-bar";
import { FilingView } from "@/components/pages/filing-view";
import type { components } from "@/lib/api/schema";
import { problem } from "@/lib/api/problem";
import type { DocumentDetail, Job, JobStage, SourceKind, StageKey } from "@/lib/api/types";
import { API } from "@/lib/api/public";

const STAGES: { key: StageKey; label: string; how: string }[] = [
  { key: "ingest", label: "Ingest", how: "Fetch, hash and store the raw file" },
  { key: "parse", label: "Parse", how: "PDF text layer; Tesseract for scanned pages" },
  { key: "entities", label: "Companies", how: "Name matching and alias resolution" },
  { key: "sentiment", label: "Sentiment", how: "FinBERT, entity-marked" },
  { key: "events", label: "Events", how: "Qwen 2.5 7B, schema-checked JSON" },
  { key: "summary", label: "Summary", how: "Llama 3.1 8B, every claim cited" },
  { key: "verify", label: "Verify", how: "Retrieval, then DeBERTa NLI" },
];

// Preview-only stage timings; a real run reports its own.
const PREVIEW_MS: Record<StageKey, number> = { ingest: 380, parse: 640, entities: 820, sentiment: 760, events: 2300, summary: 2700, verify: 1300 };



type Input = ({ kind: "text"; text: string } | { kind: "url"; url: string } | { kind: "pdf"; file: File }) & { source: SourceKind };
type AnalyzeRequest = components["schemas"]["AnalyzeRequest"];

// The rule-based event extractors key on the publisher, so the user says which one a document is from.
const SOURCES: { value: SourceKind; label: string }[] = [
  { value: "NEWS", label: "News or other" },
  { value: "SEBI", label: "SEBI order" },
  { value: "NCLT", label: "NCLT order" },
  { value: "RBI", label: "RBI press release" },
  { value: "BSE", label: "BSE announcement" },
  { value: "NSE", label: "NSE announcement" },
];

const plural = (n: number, w: string) => `${n} ${w}${n === 1 ? "" : "s"}`;
const idle = (): JobStage[] => STAGES.map(({ key }) => ({ key, status: "pending", ms: null, note: null }));

export function AnalyzeView({ preview, sample }: { preview: boolean; sample: DocumentDetail | null }) {
  const { notify } = useApp();
  const [stages, setStages] = useState<JobStage[]>(idle);
  const [phase, setPhase] = useState<"input" | "running" | "done">("input");
  const [result, setResult] = useState<DocumentDetail | null>(null);
  const timers = useRef<number[]>([]);
  const running = phase === "running";

  useEffect(() => () => timers.current.forEach((t) => window.clearTimeout(t)), []);

  const runPreview = useCallback(() => {
    if (!sample) return;
    setResult(null);
    setPhase("running");
    setStages(idle());
    notify({ title: "Job queued", body: "Running the bundled sample filing (synthetic preview).", tone: "info" });
    let t = 0;
    STAGES.forEach(({ key }, i) => {
      timers.current.push(window.setTimeout(() => setStages((s) => s.map((x) => (x.key === key ? { ...x, status: "running" } : x))), t));
      t += PREVIEW_MS[key];
      timers.current.push(
        window.setTimeout(() => {
          setStages((s) => s.map((x) => (x.key === key ? { ...x, status: "done", ms: PREVIEW_MS[key] } : x)));
          if (i === STAGES.length - 1) {
            setPhase("done");
            setResult(sample);
            const c = sample.summary?.claims ?? [];
            notify({
              title: "Analysis complete",
              body: `${plural(sample.spans.length, "mark")} · ${plural(sample.events.length, "event")} · ${plural(c.length, "claim")}, ${c.filter((x) => x.verification === "contradicted").length} contradicted`,
              tone: "ok",
            });
          }
        }, t),
      );
    });
  }, [sample, notify]);

  const runReal = useCallback(
    async (input: Input) => {
      setResult(null);
      setPhase("running");
      setStages(idle());
      try {
        let res: Response;
        if (input.kind === "pdf") {
          const form = new FormData();
          form.append("file", input.file);
          form.append("source", input.source);
          res = await fetch(`${API}/api/analyze/file`, { method: "POST", body: form });
        } else {
          const body: AnalyzeRequest = input.kind === "text" ? { text: input.text, source: input.source } : { url: input.url, source: input.source };
          res = await fetch(`${API}/api/analyze`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
        }
        if (!res.ok) throw new Error(await problem(res));
        const { jobId } = (await res.json()) as components["schemas"]["AnalyzeAccepted"];
        notify({ title: "Job queued", body: `Job ${jobId.slice(0, 8)}`, tone: "info" });
        for (;;) {
          await new Promise((r) => setTimeout(r, 1000));
          const polled = await fetch(`${API}/api/jobs/${jobId}`);
          if (!polled.ok) throw new Error(await problem(polled));
          const job = (await polled.json()) as Job;
          setStages(job.stages);
          if (job.status === "failed") throw new Error(job.error ?? job.stages.find((s) => s.status === "failed")?.note ?? "A stage failed.");
          if (job.status === "done" && job.documentId) {
            const doc = await fetch(`${API}/api/documents/${job.documentId}`);
            if (!doc.ok) throw new Error(await problem(doc));
            setResult((await doc.json()) as DocumentDetail);
            setPhase("done");
            notify({ title: "Analysis complete", tone: "ok" });
            break;
          }
        }
      } catch (e) {
        notify({ title: "The run failed", body: e instanceof Error ? e.message : "The API is not reachable.", tone: "error" });
        setPhase("input");
      }
    },
    [notify],
  );

  const mapped: Stage[] = stages.map((s, i) => ({ key: s.key, label: STAGES[i].label, how: STAGES[i].how, status: s.status, ms: s.ms, note: s.status === "failed" ? s.note : null }));
  const done = stages.filter((s) => s.status === "done").length;

  return (
    <>
      <PageHeader
        title="Analyze"
        description="Paste a disclosure, give a public URL or upload a PDF. The whole pipeline runs on this computer, and each stage reports as it finishes."
        actions={
          phase !== "input" && (
            <button
              type="button"
              disabled={running}
              onClick={() => {
                setPhase("input");
                setResult(null);
                setStages(idle());
              }}
              className="inline-flex h-10 items-center gap-2 rounded-full border border-line-strong bg-surface px-4 text-sm font-medium text-ink-2 transition-colors hover:border-brand hover:text-ink disabled:opacity-40"
            >
              <RotateCcw className="size-4" aria-hidden="true" /> Analyze another
            </button>
          )
        }
      />

      {phase === "input" && <InputCard preview={preview} hasSample={!!sample} onSample={runPreview} onRun={runReal} />}

      {phase !== "input" && (
        <section aria-label="Pipeline progress" className="fade-up rounded-2xl border border-line bg-surface p-6 shadow-1">
          <div className="mb-5 flex items-baseline justify-between gap-4">
            <h2 className="text-lg font-semibold text-ink">{running ? "Running the pipeline" : "Pipeline finished"}</h2>
            <p className="num text-sm text-ink-3">
              {done} of {stages.length} stages
            </p>
          </div>
          <StageLine stages={mapped} showHow />
        </section>
      )}

      {result && (
        <div className="fade-up mt-10">
          <FilingView doc={result} />
        </div>
      )}
    </>
  );
}

function InputCard({ preview, hasSample, onSample, onRun }: { preview: boolean; hasSample: boolean; onSample: () => void; onRun: (i: Input) => void }) {
  const [tab, setTab] = useState("text");
  const [text, setText] = useState("");
  const [url, setUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [source, setSource] = useState<SourceKind>("NEWS");
  const words = text.trim().split(/\s+/).filter(Boolean).length;
  const ready = tab === "text" ? text.trim().length > 40 : tab === "url" ? /^https?:\/\/\S+$/.test(url) : !!file;
  const field =
    "w-full rounded-xl border border-line bg-surface px-4 text-base text-ink outline-none transition-shadow focus:border-brand focus:shadow-[0_0_0_3px_var(--brand-weak)]";

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!ready || preview) return;
    onRun(tab === "text" ? { kind: "text", text, source } : tab === "url" ? { kind: "url", url, source } : { kind: "pdf", file: file!, source });
  };

  return (
    <form onSubmit={submit} className="max-w-3xl rounded-2xl border border-line bg-surface p-6 shadow-1">
      <Tabs.Root value={tab} onValueChange={setTab}>
        <TabBar
          active={tab}
          items={[
            { value: "text", label: "Paste text" },
            { value: "url", label: "Web address" },
            { value: "pdf", label: "PDF file" },
          ]}
        />
        <Tabs.Content value="text" className="pt-5 outline-none">
          <label htmlFor="an-text" className="sr-only">
            Document text
          </label>
          <textarea
            id="an-text"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Paste the full text of a filing or order…"
            className={clsx(field, "min-h-56 resize-y py-3 leading-7")}
          />
          <p className="num mt-1.5 text-right text-sm text-ink-3">{words} words</p>
        </Tabs.Content>
        <Tabs.Content value="url" className="pt-5 outline-none">
          <label htmlFor="an-url" className="mb-2 block text-sm font-medium text-ink-2">
            Public document address
          </label>
          <input id="an-url" type="url" inputMode="url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://www.sebi.gov.in/enforcement/orders/…" className={clsx(field, "h-12")} />
          <p className="mt-2 text-sm text-ink-3">robots.txt is checked before fetching; blocked pages are not retrieved.</p>
        </Tabs.Content>
        <Tabs.Content value="pdf" className="pt-5 outline-none">
          <label
            htmlFor="an-pdf"
            className="flex cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-line-strong bg-surface-2/50 px-4 py-14 text-center transition-colors hover:border-brand"
          >
            <FileUp className="size-7 text-ink-3" aria-hidden="true" />
            <span className="text-base font-medium text-ink">{file ? file.name : "Choose a PDF"}</span>
            <span className="text-sm text-ink-3">Scanned pages are read with OCR</span>
          </label>
          <input id="an-pdf" type="file" accept="application/pdf" className="sr-only" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        </Tabs.Content>
      </Tabs.Root>

      <div className="mt-5 flex flex-wrap items-end gap-x-4 gap-y-3">
        <div className="min-w-[200px]">
          <label htmlFor="an-source" className="mb-2 block text-sm font-medium text-ink-2">
            Where it is from
          </label>
          <div className="relative">
            <select id="an-source" value={source} onChange={(e) => setSource(e.target.value as SourceKind)} className={clsx(field, "h-11 cursor-pointer appearance-none pr-10")}>
              {SOURCES.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
            <ChevronDown className="pointer-events-none absolute top-1/2 right-3.5 size-4 -translate-y-1/2 text-ink-3" aria-hidden="true" />
          </div>
        </div>
        <button
          type="submit"
          disabled={!ready || preview}
          className="inline-flex h-11 items-center gap-2 rounded-full bg-brand px-6 text-base font-semibold text-white transition-[background-color,transform,opacity] duration-150 hover:bg-brand-hover active:scale-[0.98] disabled:opacity-40"
        >
          <Play className="size-4" aria-hidden="true" /> Run the pipeline
        </button>
        {preview && hasSample && (
          <button
            type="button"
            onClick={onSample}
            className="inline-flex h-11 items-center gap-2 rounded-full border border-line-strong px-5 text-base font-medium text-ink transition-colors hover:border-brand"
          >
            Run the sample filing
          </button>
        )}
      </div>
      {preview && (
        <p className="mt-4 rounded-xl bg-warn-weak px-4 py-3 text-sm text-warn">
          Preview mode cannot analyse your own input because no pipeline is connected. Run the bundled sample to see the flow.
        </p>
      )}
    </form>
  );
}
