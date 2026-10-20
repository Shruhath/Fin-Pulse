"use client";

import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";
import Link from "next/link";
import { ArrowUp, CheckCircle2, Circle, Loader2, XCircle } from "lucide-react";
import clsx from "clsx";

import { ClaimRow, filingHref } from "@/components/tiles/verified-summary";
import { SourceBadge } from "@/components/ui/source-badge";
import { Empty } from "@/components/ui/states";
import { Workspace } from "@/components/wm/workspace";
import { problem } from "@/lib/api/problem";
import { getServerTurns, getTurns, subscribe, updateTurns, type Turn } from "@/lib/ask-store";
import type { AskAnswer, AskJob, AskStage } from "@/lib/api/types";
import { fmtDay } from "@/lib/format";

const API = process.env.NEXT_PUBLIC_FINPULSE_API_URL ?? "http://127.0.0.1:8000";
const MAX_QUESTION = 500;

const STAGE_LABEL: Record<AskStage["key"], { label: string; how: string }> = {
  retrieve: { label: "find sentences", how: "BM25 and dense search over every sentence of the filings" },
  answer: { label: "write the answer", how: "the local model cites numbered sentences, or says they do not answer" },
  verify: { label: "check each claim", how: "NLI judges every claim against the sentences it cites" },
};

const WAITING: AskStage[] = (Object.keys(STAGE_LABEL) as AskStage["key"][]).map((key) => ({
  key,
  status: "pending",
  ms: null,
  note: null,
}));

const finished = (t: Turn) => !!t.error || t.job?.status === "done" || t.job?.status === "failed";
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const plural = (n: number, w: string) => `${n} ${w}${n === 1 ? "" : "s"}`;

export function AskWorkspace({ preview, suggestions }: { preview: boolean; suggestions: string[] }) {
  const turns = useSyncExternalStore(subscribe, getTurns, getServerTurns);
  const alive = useRef(true);
  const following = useRef(new Set<string>());

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

  return (
    <Workspace
      tiles={[
        {
          id: "chat",
          cls: "chat",
          title: "ask the filings",
          weight: 3,
          flush: true,
          mobileMinH: 520,
          node: <Chat turns={turns} busy={busy} preview={preview} suggestions={suggestions} onAsk={ask} />,
        },
        {
          id: "suggestions",
          cls: "list",
          title: "try asking",
          weight: 1,
          node: <Suggestions suggestions={suggestions} disabled={busy || preview} onAsk={ask} />,
        },
        {
          id: "how",
          cls: "doc",
          title: "how an answer is made",
          weight: 1.5,
          node: <How />,
        },
      ]}
    />
  );
}

function Chat({
  turns,
  busy,
  preview,
  suggestions,
  onAsk,
}: {
  turns: Turn[];
  busy: boolean;
  preview: boolean;
  suggestions: string[];
  onAsk: (q: string) => void;
}) {
  const [draft, setDraft] = useState("");
  const endRef = useRef<HTMLDivElement>(null);
  const last = turns[turns.length - 1];
  const lastState = last ? `${last.id}:${last.job?.status ?? ""}:${last.error ?? ""}` : "";

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end", behavior: "smooth" });
  }, [turns.length, lastState]);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (busy || preview || draft.trim().length < 3) return;
    onAsk(draft);
    setDraft("");
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto" aria-live="polite" aria-busy={busy}>
        {preview ? (
          <Empty>Preview mode has no pipeline, so there is nothing to ask. Start the stack with make live.</Empty>
        ) : turns.length === 0 ? (
          <div className="mx-auto max-w-[62ch] space-y-3 px-4 py-6">
            <p className="text-base text-ink">Ask a question of the collected SEBI, NCLT and RBI filings.</p>
            <p className="text-sm leading-relaxed text-ink-2">
              Every claim in an answer cites a sentence from a filing and is checked against it by an NLI model. If the filings
              do not answer, you are told so instead of getting a guess. Each question is answered on its own; earlier ones are
              not remembered.
            </p>
            {suggestions.length > 0 && (
              <ul className="flex flex-col items-start gap-1.5 pt-1">
                {suggestions.map((s) => (
                  <li key={s}>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => onAsk(s)}
                      className="border border-line-strong px-2.5 py-1.5 text-left text-sm text-ink hover:border-ring disabled:opacity-40"
                    >
                      {s}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        ) : (
          <ol className="divide-y divide-line">
            {turns.map((t) => (
              <TurnView key={t.id} turn={t} />
            ))}
          </ol>
        )}
        <div ref={endRef} />
      </div>
      <form onSubmit={submit} className="flex items-end gap-2 border-t border-line bg-surface p-2">
        <label htmlFor="ask-q" className="sr-only">
          Your question
        </label>
        <textarea
          id="ask-q"
          rows={2}
          value={draft}
          maxLength={MAX_QUESTION}
          disabled={preview}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              e.currentTarget.form?.requestSubmit();
            }
          }}
          placeholder={busy ? "Answering…" : "What action did SEBI take against…?"}
          className="min-h-12 flex-1 resize-none border border-line bg-surface-2 p-2 text-sm leading-snug text-ink outline-none focus:border-ring disabled:opacity-40"
        />
        <button
          type="submit"
          disabled={busy || preview || draft.trim().length < 3}
          aria-label="Ask"
          className="inline-flex h-12 w-10 items-center justify-center bg-accent text-ink-inverse transition-colors hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-40"
        >
          {busy ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <ArrowUp className="size-4" aria-hidden="true" />}
        </button>
      </form>
    </div>
  );
}

function TurnView({ turn }: { turn: Turn }) {
  const answer = turn.job?.answer ?? null;
  return (
    <li className="space-y-3 px-3 py-4">
      <div>
        <p className="font-mono text-2xs text-ink-3">question</p>
        <p className="mt-0.5 text-sm font-medium text-ink">{turn.question}</p>
      </div>
      {turn.error ? (
        <p role="alert" className="border border-neg/40 bg-neg-weak px-3 py-2 text-sm text-neg">
          {turn.error}
        </p>
      ) : answer ? (
        <AnswerView answer={answer} />
      ) : (
        <Progress stages={turn.job?.stages ?? WAITING} queued={!turn.job || turn.job.status === "queued"} />
      )}
    </li>
  );
}

function Progress({ stages, queued }: { stages: AskStage[]; queued: boolean }) {
  return (
    <div>
      {queued && <p className="mb-1.5 font-mono text-2xs text-ink-3">waiting for the worker…</p>}
      <ol className="space-y-1.5">
        {stages.map((s) => {
          const Icon = s.status === "done" ? CheckCircle2 : s.status === "failed" ? XCircle : s.status === "running" ? Loader2 : Circle;
          return (
            <li key={s.key} className="grid grid-cols-[16px_1fr] gap-x-2.5">
              <Icon
                className={clsx(
                  "mt-0.5 size-3.5",
                  s.status === "done" && "text-pos",
                  s.status === "failed" && "text-neg",
                  s.status === "running" && "animate-spin text-accent",
                  (s.status === "pending" || s.status === "skipped") && "text-ink-3",
                )}
                aria-label={s.status}
                role="img"
              />
              <div className="min-w-0">
                <p className={clsx("font-mono text-xs", s.status === "pending" ? "text-ink-3" : "text-ink")}>
                  {STAGE_LABEL[s.key].label}
                  {s.ms !== null && <span className="ml-2 text-ink-3">{s.ms >= 1000 ? `${(s.ms / 1000).toFixed(1)} s` : `${s.ms} ms`}</span>}
                </p>
                <p className="truncate font-mono text-[10px] text-ink-3">{s.note ?? STAGE_LABEL[s.key].how}</p>
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function AnswerView({ answer }: { answer: AskAnswer }) {
  const supported = answer.claims.filter((c) => c.verification === "entailed").length;
  const documents = new Set(answer.passages.map((p) => p.documentId)).size;
  return (
    <div className="space-y-3">
      {answer.abstained ? (
        <div className="border border-line-strong bg-surface-2 px-3 py-2.5">
          <p className="font-mono text-2xs font-semibold text-ink-2">no answer in the filings</p>
          <p className="mt-1 text-sm leading-snug text-ink">{answer.reason}</p>
        </div>
      ) : (
        <>
          <p className={clsx("font-mono text-2xs", supported === 0 ? "text-warn" : "text-ink-3")}>
            {supported === 0
              ? "No claim below could be confirmed by a filing. Read it as an unsupported draft."
              : `${supported} of ${plural(answer.claims.length, "claim")} confirmed by a cited sentence`}
          </p>
          <ol className="divide-y divide-line border border-line">
            {answer.claims.map((c) => (
              <ClaimRow key={c.id} claim={c} />
            ))}
          </ol>
        </>
      )}
      <p className="font-mono text-2xs leading-relaxed text-ink-3">
        {answer.passages.length > 0 && (
          <>
            {plural(answer.passages.length, "sentence")} from {plural(documents, "document")} ·{" "}
          </>
        )}
        {answer.entities.length > 0 && <>about {answer.entities.map((e) => e.name).join(", ")} · </>}
        {answer.sources.length > 0 && <>{answer.sources.join(", ")} only · </>}
        {answer.passages.length > 0 && <>{answer.retrieval} · {answer.model} · </>}
        {answer.seconds.toFixed(1)} s
      </p>
      {answer.passages.length > 0 && (
        <details className="group border border-line">
          <summary className="cursor-pointer px-3 py-1.5 font-mono text-2xs text-ink-2 hover:bg-surface-2">
            sentences it read ({answer.passages.length})
          </summary>
          <ol className="divide-y divide-line">
            {answer.passages.map((p) => (
              <li key={`${p.documentId}-${p.start}`} className={clsx("px-3 py-2", p.cited && "bg-ring-soft")}>
                <p className="flex items-center gap-2 font-mono text-2xs text-ink-3">
                  <span className="w-4 text-right">{p.rank}</span>
                  <SourceBadge kind={p.source} />
                  <span>{fmtDay(p.publishedAt)}</span>
                  {p.cited && <span className="text-accent-ink">cited</span>}
                </p>
                <p className="mt-1 text-xs leading-relaxed text-ink-2">{p.text}</p>
                <Link href={filingHref(p)} className="mt-1 block truncate text-xs text-link hover:underline">
                  {p.documentTitle}
                </Link>
              </li>
            ))}
          </ol>
        </details>
      )}
    </div>
  );
}

function Suggestions({ suggestions, disabled, onAsk }: { suggestions: string[]; disabled: boolean; onAsk: (q: string) => void }) {
  if (suggestions.length === 0) return <Empty>Suggestions appear once events have been extracted from the filings.</Empty>;
  return (
    <ul className="space-y-1.5">
      {suggestions.map((s) => (
        <li key={s}>
          <button
            type="button"
            disabled={disabled}
            onClick={() => onAsk(s)}
            className="w-full border border-line px-2.5 py-1.5 text-left text-sm text-ink hover:border-ring hover:bg-surface-2 disabled:opacity-40"
          >
            {s}
          </button>
        </li>
      ))}
      <li className="pt-1 font-mono text-2xs text-ink-3">Built from the newest extracted events.</li>
    </ul>
  );
}

function How() {
  return (
    <div className="space-y-3 text-sm leading-snug text-ink-2">
      <ol className="space-y-2.5">
        {(Object.keys(STAGE_LABEL) as AskStage["key"][]).map((k, i) => (
          <li key={k} className="grid grid-cols-[18px_1fr] gap-x-2">
            <span className="font-mono text-xs font-semibold text-accent-ink">{i + 1}</span>
            <span>
              <span className="font-semibold text-ink">{STAGE_LABEL[k].label}.</span> {STAGE_LABEL[k].how}.
            </span>
          </li>
        ))}
      </ol>
      <p>
        A company or publisher named in the question limits the search to filings that mention it. A claim is marked{" "}
        <span className="text-pos">supported</span>, <span className="text-neg">contradicted</span> or{" "}
        <span className="text-neu">not verified</span>; contradicted claims stay visible.
      </p>
      <p>
        Checks are sentence by sentence, so a claim that names a company the filing calls &quot;the Noticee&quot; can come out
        unverified even when it is true. This is research software, not investment advice.
      </p>
    </div>
  );
}
