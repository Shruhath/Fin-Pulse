"use client";

import { useEffect, useMemo, useRef } from "react";
import clsx from "clsx";

import { useFocus } from "@/components/linked/focus";
import { SentimentIcon } from "@/components/ui/sentiment";
import { SourceBadge } from "@/components/ui/source-badge";
import type { DocumentDetail, EntitySpan, EventRecord } from "@/lib/api/types";
import { fmtDayLong, fmtInt, fmtPct, fmtTime } from "@/lib/format";

interface Seg {
  start: number;
  end: number;
  span?: EntitySpan;
  event?: EventRecord;
  evidence: boolean;
}

/**
 * The filing text with the model's reading on top. Every highlight is drawn by
 * slicing the model's character offsets, never by searching for the surface
 * form, so a wrong offset shows up as a visibly wrong mark.
 */
export function DocReader({ doc }: { doc: DocumentDetail }) {
  const { span, entityId, setFocus } = useFocus();
  const evidenceRef = useRef<HTMLSpanElement>(null);

  const evidence = useMemo(() => {
    if (!span || span.documentId !== doc.id) return null;
    const i = doc.text.indexOf(span.text);
    return i < 0 ? null : { start: i, end: i + span.text.length };
  }, [span, doc]);

  const segs = useMemo(() => {
    const cuts = new Set<number>([0, doc.text.length]);
    for (const s of doc.spans) cuts.add(s.start).add(s.end);
    for (const e of doc.events) if (e.trigger) cuts.add(e.trigger.start).add(e.trigger.end);
    if (evidence) cuts.add(evidence.start).add(evidence.end);
    const pts = [...cuts].filter((n) => n >= 0 && n <= doc.text.length).sort((a, b) => a - b);
    const out: Seg[] = [];
    for (let i = 0; i < pts.length - 1; i++) {
      const [a, b] = [pts[i], pts[i + 1]];
      if (a === b) continue;
      out.push({
        start: a,
        end: b,
        span: doc.spans.find((s) => s.start <= a && s.end >= b),
        event: doc.events.find((e) => e.trigger && e.trigger.start <= a && e.trigger.end >= b),
        evidence: !!evidence && evidence.start <= a && evidence.end >= b,
      });
    }
    return out;
  }, [doc, evidence]);

  useEffect(() => {
    if (evidence) evidenceRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [evidence]);

  const firstEvidence = segs.find((s) => s.evidence)?.start;
  return (
    <article className="mx-auto max-w-[74ch] px-1 py-1">
      <header className="border-b border-line pb-3">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-2xs text-ink-3">
          <SourceBadge kind={doc.source} />
          <time dateTime={doc.publishedAt}>
            {fmtDayLong(doc.publishedAt)}, {fmtTime(doc.publishedAt)}
          </time>
          <span>{fmtInt(doc.words)} words</span>
          {doc.ocr && <span className="text-warn">ocr text</span>}
          <span>{doc.status}</span>
        </div>
        <h1 className="mt-2 text-lg leading-snug font-semibold text-ink">{doc.title}</h1>
        <Legend />
      </header>
      <p className="mt-4 text-[15px] leading-7 text-ink-2">
        {segs.map((s) => {
          const text = doc.text.slice(s.start, s.end);
          const isTriggerStart = s.event && s.event.trigger!.start === s.start;
          const isSpanEnd = s.span && s.span.end === s.end;
          const lit = s.span && entityId === s.span.entityId;
          return (
            <span
              key={s.start}
              ref={s.start === firstEvidence ? evidenceRef : undefined}
              className={clsx(
                s.event && "bg-accent-weak text-ink",
                s.evidence && "bg-ring-soft text-ink outline outline-1 -outline-offset-1 outline-ring/60",
              )}
            >
              {isTriggerStart && (
                <span className="mr-1 inline-flex -translate-y-px items-center border border-ring/50 px-1 font-mono text-[10px] leading-4 font-semibold text-accent-ink">
                  event · {s.event!.type}
                </span>
              )}
              {s.span ? (
                <mark
                  tabIndex={0}
                  title={`${s.span.surface} · ${s.span.sentiment} · confidence ${fmtPct(s.span.confidence)}`}
                  onPointerEnter={() => setFocus({ entityId: s.span!.entityId })}
                  onPointerLeave={() => setFocus({ entityId: null })}
                  onFocus={() => setFocus({ entityId: s.span!.entityId })}
                  onBlur={() => setFocus({ entityId: null })}
                  className={clsx(
                    "border-b-2 bg-transparent px-px font-medium text-ink outline-none",
                    s.span.sentiment === "positive" && "border-pos bg-pos-weak",
                    s.span.sentiment === "negative" && "border-neg bg-neg-weak",
                    s.span.sentiment === "neutral" && "border-neu bg-neu-weak",
                    lit && "ring-1 ring-ring",
                  )}
                >
                  {text}
                  {isSpanEnd && <SentimentIcon sentiment={s.span.sentiment} className="ml-0.5 inline size-3 -translate-y-px" />}
                </mark>
              ) : (
                text
              )}
            </span>
          );
        })}
      </p>
    </article>
  );
}

function Legend() {
  return (
    <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 font-mono text-2xs text-ink-3">
      <li className="flex items-center gap-1.5">
        <span className="h-2 w-3 border-b-2 border-pos bg-pos-weak" aria-hidden="true" /> company, positive
      </li>
      <li className="flex items-center gap-1.5">
        <span className="h-2 w-3 border-b-2 border-neg bg-neg-weak" aria-hidden="true" /> company, negative
      </li>
      <li className="flex items-center gap-1.5">
        <span className="h-2 w-3 bg-accent-weak" aria-hidden="true" /> event trigger
      </li>
      <li className="flex items-center gap-1.5">
        <span className="h-2 w-3 bg-ring-soft outline outline-1 outline-ring/60" aria-hidden="true" /> claim evidence
      </li>
    </ul>
  );
}
