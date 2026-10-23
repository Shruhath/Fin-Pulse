"use client";

import { useEffect, useMemo, useRef } from "react";
import { ExternalLink } from "lucide-react";
import clsx from "clsx";

import { Highlight } from "@/components/app/marks";
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
 * The filing text with the model's reading on top. Every mark is drawn by slicing the model's
 * character offsets, never by searching for the surface form, so a wrong offset shows up as a
 * visibly wrong mark. Evidence for a claim is the only thing that gets the highlighter.
 */
export function DocReader({
  doc,
  at,
  onExplain,
}: {
  doc: DocumentDetail;
  at?: { start: number; end: number } | null;
  onExplain?: (span: EntitySpan) => void;
}) {
  const { span, entityId, setFocus } = useFocus();

  // arriving from an answer or a claim: mark the sentence it was checked against
  useEffect(() => {
    if (at && at.end > at.start && at.end <= doc.text.length) {
      setFocus({ span: { documentId: doc.id, text: doc.text.slice(at.start, at.end), start: at.start, end: at.end } });
    }
    // once per arrival; setFocus changes identity with every focus update
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [doc.id, at?.start, at?.end]);
  const evidenceRef = useRef<HTMLSpanElement>(null);

  const evidence = useMemo(() => {
    if (!span || span.documentId !== doc.id) return null;
    const { start, end } = span;
    if (start != null && end != null && doc.text.slice(start, end) === span.text) return { start, end };
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

  const firstEvidence = segs.find((s) => s.evidence)?.start;
  useEffect(() => {
    if (evidence) evidenceRef.current?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [evidence]);

  return (
    <article className="min-w-0">
      <header className="border-b border-line pb-5">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-sm text-ink-3">
          <SourceBadge kind={doc.source} />
          <time dateTime={doc.publishedAt ?? undefined}>
            {fmtDayLong(doc.publishedAt)}
            {doc.publishedAt && `, ${fmtTime(doc.publishedAt)}`}
          </time>
          <span className="num">{fmtInt(doc.words)} words</span>
          {doc.ocr && <span className="font-medium text-warn">Scanned page, read by OCR</span>}
          {doc.url && (
            <a href={doc.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-brand-ink no-underline hover:underline">
              Original <ExternalLink className="size-3.5" aria-hidden="true" />
            </a>
          )}
        </div>
        <h1 className="display mt-3 text-[1.625rem] leading-9 text-ink">{doc.title}</h1>
        <Legend />
      </header>
      <p className="mt-6 max-w-[68ch] text-[1.0625rem] leading-8 text-ink-2">
        {segs.map((s) => {
          const text = doc.text.slice(s.start, s.end);
          const isTriggerStart = s.event && s.event.trigger!.start === s.start;
          const isSpanEnd = s.span && s.span.end === s.end;
          const lit = s.span && entityId !== null && entityId === s.span.entityId;
          const body = s.span ? (
            <mark
              tabIndex={0}
              role={onExplain && s.span.sentiment ? "button" : undefined}
              title={`${s.span.surface} · ${s.span.sentiment ?? "unscored"} · confidence ${fmtPct(s.span.confidence)}${onExplain && s.span.sentiment ? " · click to see why" : ""}`}
              onClick={() => onExplain && s.span!.sentiment && onExplain(s.span!)}
              onKeyDown={(e) => {
                if (onExplain && s.span!.sentiment && (e.key === "Enter" || e.key === " ")) {
                  e.preventDefault();
                  onExplain(s.span!);
                }
              }}
              onPointerEnter={() => setFocus({ entityId: s.span!.entityId })}
              onPointerLeave={() => setFocus({ entityId: null })}
              onFocus={() => setFocus({ entityId: s.span!.entityId })}
              onBlur={() => setFocus({ entityId: null })}
              className={clsx(
                "rounded-[5px] bg-transparent px-0.5 font-medium text-ink outline-none transition-shadow",
                onExplain && s.span.sentiment && "cursor-pointer",
                s.span.sentiment === "positive" && "underline decoration-pos decoration-2 underline-offset-4 bg-pos-weak",
                s.span.sentiment === "negative" && "underline decoration-neg decoration-2 underline-offset-4 bg-neg-weak",
                s.span.sentiment === "neutral" && "underline decoration-neu decoration-2 underline-offset-4 bg-neu-weak",
                s.span.sentiment === null && "underline decoration-line-strong decoration-2 underline-offset-4 bg-surface-2",
                lit && "shadow-[0_0_0_2px_var(--focus-ring)]",
              )}
            >
              {text}
              {isSpanEnd && <SentimentIcon sentiment={s.span.sentiment} className="ml-0.5 inline size-3.5 -translate-y-px" />}
            </mark>
          ) : (
            text
          );
          return (
            <span key={s.start} ref={s.start === firstEvidence ? evidenceRef : undefined} className={clsx(s.event && "rounded-[5px] bg-brand-weak text-ink")}>
              {isTriggerStart && (
                <span className="mr-1.5 inline-flex -translate-y-px items-center rounded-full bg-brand px-2 text-xs leading-5 font-semibold text-white">
                  {s.event!.type}
                </span>
              )}
              {s.evidence ? <Highlight on>{body}</Highlight> : body}
            </span>
          );
        })}
      </p>
    </article>
  );
}

function Legend() {
  const dot = "inline-block h-2 w-4 rounded-sm";
  return (
    <ul aria-label="What the marks mean" className="mt-4 flex flex-wrap gap-x-5 gap-y-1.5 text-sm text-ink-3">
      <li className="flex items-center gap-2">
        <span className={clsx(dot, "bg-pos-weak shadow-[inset_0_-2px_0_var(--pos)]")} aria-hidden="true" /> Company, positive
      </li>
      <li className="flex items-center gap-2">
        <span className={clsx(dot, "bg-neg-weak shadow-[inset_0_-2px_0_var(--neg)]")} aria-hidden="true" /> Company, negative
      </li>
      <li className="flex items-center gap-2">
        <span className={clsx(dot, "bg-brand-weak")} aria-hidden="true" /> Event
      </li>
      <li className="flex items-center gap-2">
        <span className={clsx(dot, "bg-hl")} aria-hidden="true" /> Evidence for a claim
      </li>
    </ul>
  );
}
