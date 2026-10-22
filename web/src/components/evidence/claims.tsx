"use client";

import { useState } from "react";
import Link from "next/link";
import { ChevronDown, Crosshair } from "lucide-react";
import clsx from "clsx";

import { useFocus } from "@/components/linked/focus";
import { Highlight, Tick, TickChip, VERDICT_LABEL } from "@/components/app/marks";
import { SourceBadge } from "@/components/ui/source-badge";
import { Empty } from "@/components/ui/states";
import type { Claim, Summary, Verification } from "@/lib/api/types";
import { NONE } from "@/lib/format";

/** The filing, opened at the sentence the claim was checked against. */
export function filingHref(ev: { documentId: string; start?: number | null; end?: number | null }) {
  const at = ev.start != null && ev.end != null ? `?at=${ev.start}-${ev.end}` : "";
  return `/filings/${ev.documentId}${at}`;
}

const ORDER: Record<Verification, number> = { contradicted: 0, unverified: 1, entailed: 2 };
const INK: Record<Verification, string> = { entailed: "text-pos", contradicted: "text-neg", unverified: "text-neu" };
const SHORT: Record<Verification, string> = { entailed: "supported", contradicted: "contradicted", unverified: "not verified" };

/**
 * A generated summary, claim by claim. Every claim shows the verdict and can open the source
 * sentence it was checked against. Contradicted claims stay on screen and come first: hiding
 * them would hide how far to trust the rest.
 */
export function VerifiedSummary({
  summary,
  currentDocumentId,
  onLocate,
}: {
  summary: Summary | null;
  currentDocumentId?: string;
  /** Called when the reader should come into view (a narrow screen shows one pane at a time). */
  onLocate?: () => void;
}) {
  if (!summary || summary.claims.length === 0) {
    return <Empty>No summary has been written for this yet.</Empty>;
  }
  const count = (v: Verification) => summary.claims.filter((c) => c.verification === v).length;
  return (
    <div>
      <div className="mb-1 flex flex-wrap items-center gap-2">
        {(["entailed", "unverified", "contradicted"] as const).map((v) => (
          <span key={v} className="inline-flex h-7 items-center gap-1 rounded-full bg-surface-2 pr-3 pl-1.5 text-sm text-ink-2">
            <Tick verdict={v} className="size-4" draw={false} />
            <span className="num font-semibold text-ink">{count(v)}</span> {SHORT[v]}
          </span>
        ))}
      </div>
      <ol className="divide-y divide-line">
        {[...summary.claims]
          .sort((a, b) => ORDER[a.verification] - ORDER[b.verification])
          .map((c) => (
            <ClaimItem key={c.id} claim={c} currentDocumentId={currentDocumentId} onLocate={onLocate} />
          ))}
      </ol>
      <p className="mt-3 text-xs text-ink-3">Written by {summary.model}. Each claim was checked against a source sentence by an NLI model.</p>
    </div>
  );
}

export function ClaimItem({
  claim,
  currentDocumentId,
  onLocate,
  defaultOpen = false,
}: {
  claim: Claim;
  currentDocumentId?: string;
  onLocate?: () => void;
  defaultOpen?: boolean;
}) {
  const { setFocus, span } = useFocus();
  const [open, setOpen] = useState(defaultOpen);
  const ev = claim.evidence;
  const here = !!ev && ev.documentId === currentDocumentId;
  const lit = !!ev && span?.text === ev.text;
  const focusEvidence = () => ev && setFocus({ span: { documentId: ev.documentId, text: ev.text, start: ev.start, end: ev.end } });

  return (
    <li
      className="py-4"
      onPointerEnter={(e) => e.pointerType === "mouse" && focusEvidence()}
      onPointerLeave={(e) => e.pointerType === "mouse" && !open && setFocus({ span: null })}
    >
      <div className="flex gap-3">
        <TickChip verdict={claim.verification} className="mt-0.5" />
        <div className="min-w-0 flex-1">
          <p className="text-base leading-6 text-ink">{claim.text}</p>
          <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
            <span className={clsx("font-medium", INK[claim.verification])}>{VERDICT_LABEL[claim.verification]}</span>
            {ev && (
              <button
                type="button"
                aria-expanded={open}
                onClick={() => {
                  if (open) {
                    setOpen(false);
                    if (lit) setFocus({ span: null });
                  } else {
                    setOpen(true);
                    focusEvidence();
                  }
                }}
                className="inline-flex items-center gap-1 rounded-full text-ink-3 transition-colors hover:text-ink"
              >
                {open ? "Hide source" : "Show source"}
                <ChevronDown className={clsx("size-4 transition-transform duration-200", open && "rotate-180")} aria-hidden="true" />
              </button>
            )}
            {here && onLocate && (
              <button
                type="button"
                onClick={() => {
                  focusEvidence();
                  onLocate();
                }}
                className="inline-flex items-center gap-1 text-brand-ink hover:underline xl:hidden"
              >
                <Crosshair className="size-4" aria-hidden="true" /> Show in text
              </button>
            )}
          </div>

          {ev ? (
            <div className={clsx("grid transition-[grid-template-rows] duration-300 ease-(--ease-out)", open ? "grid-rows-[1fr]" : "grid-rows-[0fr]")}>
              <div className="overflow-hidden" inert={!open}>
                <figure className="mt-3 rounded-xl bg-surface-2 p-4">
                  <blockquote className="text-sm leading-6 text-ink-2">
                    <Highlight on={open || lit}>“{ev.text}”</Highlight>
                  </blockquote>
                  <figcaption className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-sm text-ink-3">
                    <SourceBadge kind={ev.source} />
                    {here ? (
                      <span>This filing</span>
                    ) : (
                      <Link href={filingHref(ev)} className="min-w-0 truncate text-brand-ink hover:underline">
                        {ev.documentTitle}
                      </Link>
                    )}
                    <span className="num ml-auto">
                      support {claim.entail?.toFixed(2) ?? NONE} · conflict {claim.contradict?.toFixed(2) ?? NONE}
                    </span>
                  </figcaption>
                </figure>
              </div>
            </div>
          ) : (
            <p className="mt-2 rounded-xl border border-dashed border-line-strong px-3 py-2 text-sm text-ink-3">
              No source sentence supports this claim. It is shown so the gap is visible.
            </p>
          )}
        </div>
      </div>
    </li>
  );
}
