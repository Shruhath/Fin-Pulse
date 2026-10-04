"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import * as Tabs from "@radix-ui/react-tabs";
import { gsap } from "gsap";
import { useGSAP } from "@gsap/react";
import { CheckCircle2, Circle, FileUp, Loader2, Play, XCircle } from "lucide-react";
import clsx from "clsx";

import { DocReader } from "@/components/tiles/doc-reader";
import { VerifiedSummary } from "@/components/tiles/verified-summary";
import { Empty } from "@/components/ui/states";
import { useWM } from "@/components/wm/wm";
import { Workspace } from "@/components/wm/workspace";
import type { DocumentDetail, Job, JobStage, StageKey } from "@/lib/api/types";

const STAGES: { key: StageKey; label: string; how: string }[] = [
  { key: "ingest", label: "ingest", how: "fetch, hash, store raw" },
  { key: "parse", label: "parse", how: "PyMuPDF text layer, OCR fallback" },
  { key: "entities", label: "entities", how: "NER + alias resolution" },
  { key: "sentiment", label: "sentiment", how: "FinBERT, entity-marked" },
  { key: "events", label: "events", how: "Qwen 2.5 7B, schema JSON" },
  { key: "summary", label: "summary", how: "Llama 3.1 8B, grounded" },
  { key: "verify", label: "verify", how: "BM25 + bge-m3, DeBERTa NLI" },
];

// Preview-only stage timings; a real run reports its own.
const PREVIEW_MS: Record<StageKey, number> = { ingest: 380, parse: 640, entities: 820, sentiment: 760, events: 2300, summary: 2700, verify: 1300 };

const API = process.env.NEXT_PUBLIC_FINPULSE_API_URL ?? "http://127.0.0.1:8000";

type Input = { kind: "text"; text: string } | { kind: "url"; url: string } | { kind: "pdf"; file: File };

const plural = (n: number, w: string) => `${n} ${w}${n === 1 ? "" : "s"}`;

const idle = (): JobStage[] => STAGES.map(({ key }) => ({ key, status: "pending", ms: null, note: null }));

export function AnalyzeWorkspace({ preview, sample }: { preview: boolean; sample: DocumentDetail | null }) {
  const { notify } = useWM();
  const [stages, setStages] = useState<JobStage[]>(idle);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<DocumentDetail | null>(null);
  const timers = useRef<number[]>([]);

  useEffect(() => () => timers.current.forEach((t) => window.clearTimeout(t)), []);

  const runPreview = useCallback(() => {
    if (!sample) return;
    setResult(null);
    setRunning(true);
    setStages(idle());
    notify({ app: "pipeline", title: "Job queued", body: "Running the bundled sample filing (synthetic preview).", tone: "info" });
    let t = 0;
    STAGES.forEach(({ key }, i) => {
      timers.current.push(
        window.setTimeout(() => setStages((s) => s.map((x) => (x.key === key ? { ...x, status: "running" } : x))), t),
      );
      t += PREVIEW_MS[key];
      timers.current.push(
        window.setTimeout(() => {
          setStages((s) => s.map((x) => (x.key === key ? { ...x, status: "done", ms: PREVIEW_MS[key] } : x)));
          if (i === STAGES.length - 1) {
            setRunning(false);
            setResult(sample);
            const c = sample.summary?.claims ?? [];
            notify({
              app: "pipeline",
              title: "Analysis complete",
              body: `${plural(sample.spans.length, "span")} · ${plural(sample.events.length, "event")} · ${plural(c.length, "claim")}, ${c.filter((x) => x.verification === "contradicted").length} contradicted`,
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
      setRunning(true);
      setStages(idle());
      try {
        const res =
          input.kind === "pdf"
            ? await fetch(`${API}/api/analyze`, { method: "POST", body: (() => { const f = new FormData(); f.append("file", input.file); return f; })() })
            : await fetch(`${API}/api/analyze`, {
                method: "POST",
                headers: { "content-type": "application/json" },
                body: JSON.stringify(input.kind === "text" ? { text: input.text } : { url: input.url }),
              });
        if (!res.ok) throw new Error(`The API answered ${res.status}.`);
        const { job_id } = (await res.json()) as { job_id: string };
        notify({ app: "pipeline", title: "Job queued", body: `Job ${job_id.slice(0, 8)}`, tone: "info" });
        for (;;) {
          await new Promise((r) => setTimeout(r, 1000));
          const job = (await (await fetch(`${API}/api/jobs/${job_id}`)).json()) as Job;
          setStages(job.stages);
          if (job.status === "failed") throw new Error(job.stages.find((s) => s.status === "failed")?.note ?? "A stage failed.");
          if (job.status === "done" && job.documentId) {
            setResult((await (await fetch(`${API}/api/documents/${job.documentId}`)).json()) as DocumentDetail);
            notify({ app: "pipeline", title: "Analysis complete", tone: "ok" });
            break;
          }
        }
      } catch (e) {
        notify({ app: "pipeline", title: "Run failed", body: e instanceof Error ? e.message : "The API is not reachable.", tone: "error" });
      } finally {
        setRunning(false);
      }
    },
    [notify],
  );

  return (
    <Workspace
      tiles={[
        {
          id: "input",
          cls: "input",
          title: "new document",
          mobileMinH: 360,
          node: <InputPane preview={preview} running={running} onSample={runPreview} onRun={runReal} hasSample={!!sample} />,
        },
        {
          id: "pipeline",
          cls: "pipeline",
          title: running ? "running" : result ? "complete" : "idle",
          weight: 2.5,
          node: <Pipeline stages={stages} />,
        },
        {
          id: "result",
          cls: "reader",
          title: result ? result.title.toLowerCase() : "result",
          weight: 1.5,
          node: result ? <DocReader doc={result} /> : <Empty>The analysed document appears here, spans and events marked.</Empty>,
        },
        {
          id: "result-claims",
          cls: "claims",
          title: "verified summary",
          weight: 1.4,
          flush: true,
          node: result ? (
            <VerifiedSummary summary={result.summary} currentDocumentId={result.id} />
          ) : (
            <Empty>Claims and their verdicts appear after the verify stage.</Empty>
          ),
        },
      ]}
    />
  );
}

function InputPane({
  preview,
  running,
  hasSample,
  onSample,
  onRun,
}: {
  preview: boolean;
  running: boolean;
  hasSample: boolean;
  onSample: () => void;
  onRun: (i: Input) => void;
}) {
  const [tab, setTab] = useState("text");
  const [text, setText] = useState("");
  const [url, setUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const ready = tab === "text" ? text.trim().length > 40 : tab === "url" ? /^https?:\/\/\S+$/.test(url) : !!file;

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!ready || preview) return;
    onRun(tab === "text" ? { kind: "text", text } : tab === "url" ? { kind: "url", url } : { kind: "pdf", file: file! });
  };

  return (
    <form onSubmit={submit} className="flex h-full flex-col gap-3">
      <p className="text-sm text-ink-2">
        Paste a disclosure, give a public URL (BSE, SEBI, RBI, NCLT), or upload a PDF. The full pipeline runs locally and every
        stage reports as it finishes.
      </p>
      <Tabs.Root value={tab} onValueChange={setTab} className="flex min-h-0 flex-1 flex-col">
        <Tabs.List aria-label="Input type" className="flex border-b border-line">
          {[
            ["text", "Text"],
            ["url", "URL"],
            ["pdf", "PDF"],
          ].map(([v, l]) => (
            <Tabs.Trigger
              key={v}
              value={v}
              className="-mb-px border-b-2 border-transparent px-3 py-1.5 font-mono text-xs text-ink-3 hover:text-ink data-[state=active]:border-accent data-[state=active]:text-ink"
            >
              {l}
            </Tabs.Trigger>
          ))}
        </Tabs.List>
        <Tabs.Content value="text" className="flex min-h-0 flex-1 flex-col pt-3">
          <label htmlFor="an-text" className="sr-only">
            Document text
          </label>
          <textarea
            id="an-text"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Paste the full text of a filing or order…"
            className="min-h-40 flex-1 resize-none border border-line bg-surface-2 p-3 font-sans text-sm leading-relaxed text-ink outline-none focus:border-ring"
          />
          <p className="mt-1 text-right font-mono text-2xs text-ink-3">{text.trim().split(/\s+/).filter(Boolean).length} words</p>
        </Tabs.Content>
        <Tabs.Content value="url" className="pt-3">
          <label htmlFor="an-url" className="mb-1.5 block font-mono text-2xs text-ink-3">
            public document URL
          </label>
          <input
            id="an-url"
            type="url"
            inputMode="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://www.sebi.gov.in/enforcement/orders/…"
            className="h-9 w-full border border-line bg-surface-2 px-3 font-mono text-sm text-ink outline-none focus:border-ring"
          />
          <p className="mt-2 text-xs text-ink-3">robots.txt is checked before fetching; blocked pages are not retrieved.</p>
        </Tabs.Content>
        <Tabs.Content value="pdf" className="pt-3">
          <label
            htmlFor="an-pdf"
            className="flex cursor-pointer flex-col items-center justify-center gap-2 border border-dashed border-line-strong bg-surface-2 px-4 py-10 text-center hover:border-ring"
          >
            <FileUp className="size-5 text-ink-3" aria-hidden="true" />
            <span className="text-sm text-ink">{file ? file.name : "Choose a PDF"}</span>
            <span className="font-mono text-2xs text-ink-3">scanned orders go through OCR</span>
          </label>
          <input id="an-pdf" type="file" accept="application/pdf" className="sr-only" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        </Tabs.Content>
      </Tabs.Root>
      {preview && (
        <p className="border border-warn/40 bg-warn-weak px-3 py-2 text-xs text-warn">
          Preview mode cannot analyse your own input: no pipeline is connected. Run the bundled sample to see the flow.
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        <button
          type="submit"
          disabled={!ready || running || preview}
          className="inline-flex h-8 items-center gap-2 bg-accent px-3 font-mono text-xs font-semibold text-ink-inverse transition-colors hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-40"
        >
          {running ? <Loader2 className="size-3.5 animate-spin" /> : <Play className="size-3.5" />}
          run pipeline
        </button>
        {preview && hasSample && (
          <button
            type="button"
            onClick={onSample}
            disabled={running}
            className="inline-flex h-8 items-center gap-2 border border-line-strong px-3 font-mono text-xs text-ink hover:border-ring disabled:opacity-40"
          >
            run the sample filing
          </button>
        )}
      </div>
    </form>
  );
}

function Pipeline({ stages }: { stages: JobStage[] }) {
  const ref = useRef<HTMLOListElement>(null);
  const done = stages.filter((s) => s.status === "done").length;
  const total = stages.reduce((a, s) => a + (s.ms ?? 0), 0);
  const lastDone = stages.map((s) => s.status).lastIndexOf("done");

  // The running stage's bar sweeps; finished stages fill once.
  useGSAP(
    () => {
      const mm = gsap.matchMedia();
      mm.add("(prefers-reduced-motion: no-preference)", () => {
        gsap.fromTo(".pl-run", { xPercent: -100 }, { xPercent: 100, duration: 1.1, ease: "power1.inOut", repeat: -1 });
        gsap.fromTo(".pl-fresh", { scaleX: 0 }, { scaleX: 1, duration: 0.45, ease: "expo.out", transformOrigin: "left" });
      });
      return () => mm.revert();
    },
    { scope: ref, dependencies: [stages], revertOnUpdate: true },
  );

  return (
    <div className="flex h-full flex-col">
      <div className="mb-3 flex items-baseline justify-between font-mono text-2xs text-ink-3">
        <span>
          <span className="text-ink">{done}</span>/{stages.length} stages
        </span>
        {total > 0 && <span>{(total / 1000).toFixed(1)} s</span>}
      </div>
      <ol ref={ref} className="space-y-2">
        {stages.map((s, i) => {
          const meta = STAGES[i];
          const Icon = s.status === "done" ? CheckCircle2 : s.status === "failed" ? XCircle : s.status === "running" ? Loader2 : Circle;
          return (
            <li key={s.key} className="grid grid-cols-[16px_88px_1fr_auto] items-center gap-x-3">
              <Icon
                className={clsx(
                  "size-3.5",
                  s.status === "done" && "text-pos",
                  s.status === "failed" && "text-neg",
                  s.status === "running" && "animate-spin text-accent",
                  s.status === "pending" && "text-ink-3",
                )}
                aria-label={s.status}
                role="img"
              />
              <span className={clsx("font-mono text-xs", s.status === "pending" ? "text-ink-3" : "text-ink")}>{meta.label}</span>
              <span className="relative h-1.5 overflow-hidden bg-surface-2">
                {s.status === "running" && <span className="pl-run absolute inset-y-0 w-1/2 bg-accent" />}
                {s.status === "done" && <span className={clsx("absolute inset-0 bg-pos/70", i === lastDone && "pl-fresh")} />}
                {s.status === "failed" && <span className="absolute inset-0 bg-neg/70" />}
              </span>
              <span className="w-14 text-right font-mono text-2xs whitespace-nowrap text-ink-3">{s.ms === null ? "" : s.ms >= 1000 ? `${(s.ms / 1000).toFixed(1)} s` : `${s.ms} ms`}</span>
              <span className="col-start-2 col-end-5 -mt-1 truncate font-mono text-[10px] text-ink-3">{s.note ?? meta.how}</span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
