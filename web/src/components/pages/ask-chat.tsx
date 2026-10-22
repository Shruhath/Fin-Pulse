"use client";

import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowUp, ChevronDown, Loader2, Mic, Square, Trash2, Volume2, VolumeX } from "lucide-react";
import clsx from "clsx";

import { PageHeader } from "@/components/app/page-header";
import { StageLine, type Stage } from "@/components/app/stage-line";
import { ClaimItem, filingHref } from "@/components/evidence/claims";
import { SourceBadge } from "@/components/ui/source-badge";
import { problem } from "@/lib/api/problem";
import { getServerTurns, getTurns, subscribe, updateTurns, type Turn } from "@/lib/ask-store";
import type { AskAnswer, AskJob, AskStage, Transcription } from "@/lib/api/types";
import { fmtDay } from "@/lib/format";
import { useBooleanPref } from "@/lib/pref-store";
import { speak, spokenAnswer, stopSpeaking, useCanSpeak } from "@/lib/speak";
import { describeMicError, listen, type Listener, useVoiceSupported } from "@/lib/voice";

const API = process.env.NEXT_PUBLIC_FINPULSE_API_URL ?? "http://127.0.0.1:8000";
const MAX_QUESTION = 500;

const STAGE_LABEL: Record<AskStage["key"], { label: string; how: string }> = {
  retrieve: { label: "Find sentences", how: "Searches every sentence of the filings, by words and by meaning." },
  answer: { label: "Write the answer", how: "A local model cites numbered sentences, or says they do not answer." },
  verify: { label: "Check each claim", how: "An NLI model judges every claim against the sentence it cites." },
};
const STAGE_KEYS = Object.keys(STAGE_LABEL) as AskStage["key"][];

const WAITING: AskStage[] = STAGE_KEYS.map((key) => ({ key, status: "pending", ms: null, note: null }));

const finished = (t: Turn) => !!t.error || t.job?.status === "done" || t.job?.status === "failed";
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const plural = (n: number, w: string) => `${n} ${w}${n === 1 ? "" : "s"}`;

export function AskChat({
  preview,
  suggestions,
  voiceModel,
  initialQuestion,
}: {
  preview: boolean;
  suggestions: string[];
  voiceModel: string | null;
  initialQuestion: string | null;
}) {
  const router = useRouter();
  const turns = useSyncExternalStore(subscribe, getTurns, getServerTurns);
  const alive = useRef(true);
  const following = useRef(new Set<string>());
  const handedOver = useRef(false);

  const patch = useCallback((id: string, change: Partial<Turn>) => {
    updateTurns((all) => all.map((t) => (t.id === id ? { ...t, ...change } : t)));
  }, []);

  /** Poll one question until the worker has finished it. */
  const follow = useCallback(
    async (id: string, jobId: string) => {
      if (following.current.has(id)) return;
      following.current.add(id);
      try {
        for (;;) {
          const res = await fetch(`${API}/api/ask/${jobId}`, { cache: "no-store" });
          if (!res.ok) throw new Error(await problem(res));
          const job = (await res.json()) as AskJob;
          if (!alive.current) return;
          patch(id, { job, error: job.status === "failed" ? (job.error ?? "The question failed.") : null });
          if (job.status === "done" || job.status === "failed") return;
          await sleep(job.status === "queued" ? 1200 : 700);
        }
      } catch (e) {
        if (alive.current) patch(id, { error: e instanceof Error ? e.message : "The API is not reachable." });
      } finally {
        following.current.delete(id);
      }
    },
    [patch],
  );

  // a question still being answered when the page was left is picked up again
  useEffect(() => {
    alive.current = true;
    for (const t of getTurns()) if (t.jobId && !finished(t)) void follow(t.id, t.jobId);
    return () => {
      alive.current = false;
    };
  }, [follow]);

  const busy = turns.some((t) => !finished(t));

  const ask = useCallback(
    async (raw: string) => {
      const question = raw.trim().replace(/\s+/g, " ");
      if (question.length < 3 || preview) return;
      const id = `${Date.now()}`;
      updateTurns((all) => [...all, { id, question, jobId: null, job: null, error: null }]);
      try {
        const res = await fetch(`${API}/api/ask`, {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ question }),
        });
        if (!res.ok) throw new Error(await problem(res));
        const { jobId } = (await res.json()) as { jobId: string };
        patch(id, { jobId });
        void follow(id, jobId);
      } catch (e) {
        patch(id, { error: e instanceof Error ? e.message : "The API is not reachable." });
      }
    },
    [follow, patch, preview],
  );

  // A question handed over from Home or the search box is asked once, then the address is tidied.
  useEffect(() => {
    if (!initialQuestion || handedOver.current) return;
    handedOver.current = true;
    void ask(initialQuestion);
    router.replace("/ask", { scroll: false });
  }, [initialQuestion, ask, router]);

  const hasTurns = turns.length > 0;

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader
        title="Ask"
        description="Ask the SEBI, NCLT and RBI filings a question. Every claim in the answer cites a sentence and is checked against it; if the filings do not answer, you are told so."
        actions={
          hasTurns && (
            <button
              type="button"
              onClick={() => updateTurns(() => [])}
              disabled={busy}
              className="inline-flex h-10 items-center gap-2 rounded-full border border-line-strong bg-surface px-4 text-sm font-medium text-ink-2 transition-colors hover:border-brand hover:text-ink disabled:opacity-40"
            >
              <Trash2 className="size-4" aria-hidden="true" /> Clear
            </button>
          )
        }
      />

      {preview && (
        <p className="mb-6 rounded-2xl bg-warn-weak px-5 py-4 text-base text-warn">
          Preview mode has no pipeline, so there is nothing to ask. Start the stack with <code className="font-mono text-sm">make live</code>.
        </p>
      )}

      {hasTurns && (
        <ol aria-live="polite" aria-busy={busy} className="space-y-10 pb-10">
          {turns.map((t) => (
            <TurnView key={t.id} turn={t} />
          ))}
        </ol>
      )}

      <div className={clsx(hasTurns && "sticky bottom-[4.5rem] z-10 -mx-4 bg-gradient-to-t from-bg from-70% to-transparent px-4 pt-8 pb-3 sm:-mx-8 sm:px-8 lg:bottom-0 lg:pb-6")}>
        <Composer turns={turns} busy={busy} preview={preview} voiceModel={voiceModel} onAsk={ask} />
      </div>

      {!hasTurns && (
        <div className="mt-10 space-y-12">
          {suggestions.length > 0 && !preview && (
            <section>
              <h2 className="mb-3 text-lg font-semibold text-ink">Try asking</h2>
              <ul className="flex flex-col items-start gap-2">
                {suggestions.map((s) => (
                  <li key={s} className="max-w-full">
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => ask(s)}
                      className="max-w-full rounded-2xl border border-line bg-surface px-4 py-2.5 text-left text-base text-ink transition-[border-color,transform] duration-150 hover:border-brand active:scale-[0.99] disabled:opacity-40"
                    >
                      {s}
                    </button>
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-sm text-ink-3">Built from the newest extracted events.</p>
            </section>
          )}
          <section>
            <h2 className="mb-4 text-lg font-semibold text-ink">How an answer is made</h2>
            <StageLine showHow stages={STAGE_KEYS.map((k) => ({ key: k, label: STAGE_LABEL[k].label, how: STAGE_LABEL[k].how, status: "pending" as const }))} />
            <p className="mt-6 max-w-[64ch] text-sm leading-6 text-ink-3">
              A company or publisher named in the question limits the search to filings that mention it. Checks are sentence by sentence, so a claim
              that names a company the filing calls “the Noticee” can come out unverified even when it is true. Each question is answered on its own.
              This is research software, not investment advice.
            </p>
          </section>
        </div>
      )}
    </div>
  );
}

function Composer({
  turns,
  busy,
  preview,
  voiceModel,
  onAsk,
}: {
  turns: Turn[];
  busy: boolean;
  preview: boolean;
  voiceModel: string | null;
  onAsk: (q: string) => void;
}) {
  const [draft, setDraft] = useState("");
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const [mic, setMic] = useState<"idle" | "listening" | "transcribing">("idle");
  const [level, setLevel] = useState(0);
  const [note, setNote] = useState<string | null>(null);
  const [autoSend, setAutoSend] = useBooleanPref("finpulse.ask.autosend");
  const listener = useRef<Listener | null>(null);
  const cancelled = useRef(false);
  const supported = useVoiceSupported();
  const micReady = !preview && !!voiceModel && supported;
  const micTitle = preview
    ? "Preview mode has no pipeline"
    : !supported
      ? "Voice needs a microphone and a secure page (localhost or https)"
      : !voiceModel
        ? "The speech model is not installed (scripts/fetch_models.py asr)"
        : mic === "listening"
          ? "Stop and use what you said"
          : "Speak your question";

  // leaving the page ends a recording in progress
  useEffect(() => () => listener.current?.cancel(), []);

  const last = turns[turns.length - 1];
  const lastState = last ? `${last.id}:${last.job?.status ?? ""}:${last.error ?? ""}` : "";
  useEffect(() => {
    if (turns.length) endRef.current?.scrollIntoView({ block: "end", behavior: "smooth" });
  }, [turns.length, lastState]);

  // the box grows with what is typed, up to a few lines
  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 132)}px`;
  }, [draft]);

  const speakQuestion = async () => {
    if (mic === "listening") return listener.current?.stop();
    if (mic !== "idle") return;
    stopSpeaking();
    cancelled.current = false;
    setNote(null);
    try {
      const l = await listen({ onLevel: setLevel });
      listener.current = l;
      setMic("listening");
      const wav = await l.result;
      listener.current = null;
      if (cancelled.current) return setMic("idle");
      if (!wav) {
        setMic("idle");
        return setNote("I did not hear anything. Try again, closer to the microphone.");
      }
      setMic("transcribing");
      const res = await fetch(`${API}/api/transcribe`, { method: "POST", headers: { "content-type": "audio/wav" }, body: wav });
      if (!res.ok) throw new Error(await problem(res));
      const { text } = (await res.json()) as Transcription;
      setMic("idle");
      if (!text.trim()) return setNote("I could not make out any words. Try again.");
      if (autoSend && !busy) {
        setDraft("");
        onAsk(text);
      } else {
        setDraft(text);
        setNote(`Heard: “${text}”. Edit it if needed, then press Enter.`);
        inputRef.current?.focus();
      }
    } catch (e) {
      listener.current = null;
      setMic("idle");
      setNote(describeMicError(e));
    }
  };

  const cancelListening = () => {
    cancelled.current = true;
    listener.current?.cancel();
  };

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (busy || preview || draft.trim().length < 3) return;
    onAsk(draft);
    setDraft("");
  };

  return (
    <form onSubmit={submit}>
      <div ref={endRef} />
      <div className="flex items-end gap-2 rounded-3xl border border-line bg-surface p-2 pl-5 shadow-2 transition-shadow duration-200 focus-within:border-brand focus-within:shadow-[0_0_0_4px_var(--brand-weak)]">
        <label htmlFor="ask-q" className="sr-only">
          Your question
        </label>
        <textarea
          id="ask-q"
          ref={inputRef}
          rows={1}
          value={draft}
          maxLength={MAX_QUESTION}
          disabled={preview}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              e.currentTarget.form?.requestSubmit();
            } else if (e.key === "Escape" && mic === "listening") {
              cancelListening();
            }
          }}
          placeholder={busy ? "Answering…" : mic === "listening" ? "Listening…" : "Ask the filings a question"}
          className="max-h-[132px] min-h-11 flex-1 resize-none bg-transparent py-2.5 text-md leading-6 text-ink outline-none disabled:opacity-40"
        />
        <button
          type="button"
          onClick={speakQuestion}
          disabled={!micReady || mic === "transcribing"}
          aria-label={mic === "listening" ? "Stop listening" : "Speak your question"}
          aria-pressed={mic === "listening"}
          title={micTitle}
          className={clsx(
            "inline-flex size-11 shrink-0 items-center justify-center rounded-full transition-colors disabled:cursor-not-allowed disabled:opacity-35",
            mic === "listening" ? "bg-neg-weak text-neg" : "text-ink-2 hover:bg-surface-2",
          )}
        >
          {mic === "listening" ? <Square className="size-5" aria-hidden="true" /> : <Mic className="size-5" aria-hidden="true" />}
        </button>
        <button
          type="submit"
          disabled={busy || preview || draft.trim().length < 3}
          aria-label="Ask"
          className="inline-flex size-11 shrink-0 items-center justify-center rounded-full bg-brand text-white transition-[background-color,transform,opacity] duration-150 hover:bg-brand-hover active:scale-95 disabled:cursor-not-allowed disabled:opacity-35"
        >
          {busy ? <Loader2 className="size-5 animate-spin" aria-hidden="true" /> : <ArrowUp className="size-5" aria-hidden="true" />}
        </button>
      </div>
      <div role="status" className="flex min-h-6 flex-wrap items-center gap-x-4 gap-y-1 px-4 pt-2 text-sm text-ink-3">
        {mic === "listening" ? (
          <>
            <span className="h-1.5 w-24 overflow-hidden rounded-full bg-surface-3" aria-hidden="true">
              <span className="block h-full rounded-full bg-neg transition-[width] duration-75" style={{ width: `${Math.round(level * 100)}%` }} />
            </span>
            <span className="text-ink">Listening. It stops when you pause.</span>
            <button type="button" onClick={cancelListening} className="text-brand-ink hover:underline">
              Cancel
            </button>
          </>
        ) : mic === "transcribing" ? (
          <>
            <Loader2 className="size-4 animate-spin" aria-hidden="true" />
            <span>Turning your speech into text on this computer…</span>
          </>
        ) : (
          note
        )}
        {micReady && (
          <label className="ml-auto flex cursor-pointer items-center gap-2">
            <input type="checkbox" checked={autoSend} onChange={(e) => setAutoSend(e.target.checked)} className="check" />
            Send when I stop talking
          </label>
        )}
      </div>
    </form>
  );
}

function TurnView({ turn }: { turn: Turn }) {
  const answer = turn.job?.answer ?? null;
  return (
    <li className="fade-up">
      <h2 className="text-lg leading-7 font-semibold text-ink">{turn.question}</h2>
      <div className="mt-4 rounded-2xl border border-line bg-surface p-5 shadow-1 sm:p-6">
        {turn.error ? (
          <p role="alert" className="text-base text-neg">
            {turn.error}
          </p>
        ) : answer ? (
          <AnswerView answer={answer} />
        ) : (
          <Progress stages={turn.job?.stages ?? WAITING} queued={!turn.job || turn.job.status === "queued"} />
        )}
      </div>
    </li>
  );
}

function Progress({ stages, queued }: { stages: AskStage[]; queued: boolean }) {
  const mapped: Stage[] = stages.map((s) => ({
    key: s.key,
    label: STAGE_LABEL[s.key].label,
    how: s.note ?? STAGE_LABEL[s.key].how,
    status: s.status,
    ms: s.ms,
    note: s.status === "failed" ? s.note : null,
  }));
  return (
    <div>
      {queued && <p className="mb-4 text-sm text-ink-3">Waiting for the worker to pick this up…</p>}
      <StageLine stages={mapped} />
    </div>
  );
}

function ListenButton({ answer }: { answer: AskAnswer }) {
  const canSpeak = useCanSpeak();
  const [speaking, setSpeaking] = useState(false);
  useEffect(() => () => stopSpeaking(), []);
  if (!canSpeak) return null;
  return (
    <button
      type="button"
      onClick={() => {
        if (speaking) {
          stopSpeaking();
          setSpeaking(false);
        } else {
          setSpeaking(true);
          speak(spokenAnswer(answer), () => setSpeaking(false));
        }
      }}
      className="inline-flex items-center gap-1.5 text-brand-ink hover:underline"
    >
      {speaking ? <VolumeX className="size-4" aria-hidden="true" /> : <Volume2 className="size-4" aria-hidden="true" />}
      {speaking ? "Stop" : "Listen"}
    </button>
  );
}

function AnswerView({ answer }: { answer: AskAnswer }) {
  const supported = answer.claims.filter((c) => c.verification === "entailed").length;
  const documents = new Set(answer.passages.map((p) => p.documentId)).size;
  return (
    <div className="space-y-5">
      {answer.abstained ? (
        <div className="rounded-xl bg-surface-2 px-4 py-3.5">
          <p className="text-sm font-semibold text-ink-2">The filings do not answer this</p>
          <p className="mt-1 text-base text-ink">{answer.reason}</p>
        </div>
      ) : (
        <>
          <p className={clsx("text-sm font-medium", supported === 0 ? "text-warn" : "text-ink-3")}>
            {supported === 0
              ? "No claim below could be confirmed by a filing. Read it as an unsupported draft."
              : `${supported} of ${plural(answer.claims.length, "claim")} confirmed by a cited sentence`}
          </p>
          <ol className="-my-2 divide-y divide-line">
            {answer.claims.map((c, i) => (
              <ClaimItem key={c.id} claim={c} defaultOpen={i === 0 && c.verification === "entailed"} />
            ))}
          </ol>
        </>
      )}
      {answer.abstained && answer.claims.length > 0 && (
        <Disclosure label={`The draft, which no filing confirmed (${answer.claims.length})`}>
          <ol className="divide-y divide-line">
            {answer.claims.map((c) => (
              <ClaimItem key={c.id} claim={c} />
            ))}
          </ol>
        </Disclosure>
      )}
      <p className="flex flex-wrap items-center gap-x-4 gap-y-1.5 border-t border-line pt-4 text-sm text-ink-3">
        <span>
          {answer.passages.length > 0 && <>{plural(answer.passages.length, "sentence")} from {plural(documents, "document")}</>}
          {answer.entities.length > 0 && <> · about {answer.entities.map((e) => e.name).join(", ")}</>}
          {answer.sources.length > 0 && <> · {answer.sources.join(", ")} only</>}
          {answer.passages.length > 0 && <> · {answer.retrieval} · {answer.model}</>}
          <> · {answer.seconds.toFixed(1)} s</>
        </span>
        <ListenButton answer={answer} />
      </p>
      {answer.passages.length > 0 && (
        <Disclosure label={`Sentences it read (${answer.passages.length})`}>
          <ol className="divide-y divide-line">
            {answer.passages.map((p) => (
              <li key={`${p.documentId}-${p.start}`} className="py-3">
                <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-ink-3">
                  <span className="num w-5 text-right">{p.rank}</span>
                  <SourceBadge kind={p.source} />
                  <span>{fmtDay(p.publishedAt)}</span>
                  {p.cited && <span className="rounded-full bg-hl-solid px-2 text-xs font-semibold text-hl-solid-ink">Cited</span>}
                </p>
                <p className="mt-1.5 text-sm leading-6 text-ink-2">{p.text}</p>
                <Link href={filingHref(p)} className="mt-1 block truncate text-sm text-brand-ink hover:underline">
                  {p.documentTitle}
                </Link>
              </li>
            ))}
          </ol>
        </Disclosure>
      )}
    </div>
  );
}

function Disclosure({ label, children }: { label: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <button type="button" aria-expanded={open} onClick={() => setOpen(!open)} className="inline-flex items-center gap-1.5 text-sm font-medium text-ink-2 hover:text-ink">
        {label}
        <ChevronDown className={clsx("size-4 transition-transform duration-200", open && "rotate-180")} aria-hidden="true" />
      </button>
      <div className={clsx("grid transition-[grid-template-rows] duration-300 ease-(--ease-out)", open ? "grid-rows-[1fr]" : "grid-rows-[0fr]")}>
        <div className="overflow-hidden" inert={!open}>
          <div className="pt-2">{children}</div>
        </div>
      </div>
    </div>
  );
}
