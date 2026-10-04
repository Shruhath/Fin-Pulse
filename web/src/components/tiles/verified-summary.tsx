"use client";

import Link from "next/link";
import { CheckCircle2, CircleHelp, XCircle } from "lucide-react";
import clsx from "clsx";

import { useFocus } from "@/components/linked/focus";
import { SourceBadge } from "@/components/ui/source-badge";
import { Empty } from "@/components/ui/states";
import type { Claim, Summary, Verification } from "@/lib/api/types";

const V: Record<Verification, { icon: typeof CheckCircle2; label: string; ink: string }> = {
  entailed: { icon: CheckCircle2, label: "supported by source", ink: "text-pos" },
  contradicted: { icon: XCircle, label: "contradicted by source", ink: "text-neg" },
  unverified: { icon: CircleHelp, label: "not verified", ink: "text-neu" },
};

/**
 * A generated summary, claim by claim. Every claim shows the NLI verdict and
 * the source sentence it was checked against. Contradicted claims stay on
 * screen, struck through: hiding them would hide how far to trust the rest.
 */
export function VerifiedSummary({ summary, currentDocumentId }: { summary: Summary | null; currentDocumentId?: string }) {
  if (!summary || summary.claims.length === 0) {
    return <Empty>No summary has been generated for this yet.</Empty>;
  }
  const count = (v: Verification) => summary.claims.filter((c) => c.verification === v).length;
  return (
    <div>
      <div className="sticky top-0 z-[1] flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-line bg-surface px-3 py-2 font-mono text-2xs text-ink-3">
        {(Object.keys(V) as Verification[]).map((v) => {
          const { icon: Icon, ink } = V[v];
          return (
            <span key={v} className="flex items-center gap-1">
              <Icon className={clsx("size-3", ink)} aria-hidden="true" />
              <span className="text-ink-2">{count(v)}</span> {v}
            </span>
          );
        })}
        <span className="ml-auto truncate">{summary.model}</span>
      </div>
      <ol className="divide-y divide-line">
        {summary.claims.map((c) => (
          <ClaimRow key={c.id} claim={c} currentDocumentId={currentDocumentId} />
        ))}
      </ol>
    </div>
  );
}

function ClaimRow({ claim, currentDocumentId }: { claim: Claim; currentDocumentId?: string }) {
  const { setFocus, span } = useFocus();
  const { icon: Icon, label, ink } = V[claim.verification];
  const ev = claim.evidence;
  const lit = !!ev && span?.text === ev.text;
  return (
    <li className="grid grid-cols-[16px_1fr] gap-x-2.5 px-3 py-3">
      <Icon className={clsx("mt-0.5 size-4", ink)} aria-label={label} role="img" strokeWidth={2} />
      <div className="min-w-0">
        <p
          className={clsx(
            "text-sm leading-snug text-ink",
            claim.verification === "contradicted" && "line-through decoration-neg/70 decoration-1",
          )}
        >
          {claim.text}
        </p>
        <p className="mt-1 font-mono text-2xs text-ink-3">
          <span className={ink}>{label}</span>
          <span className="px-1.5">·</span>entail {claim.entail.toFixed(2)}
          <span className="px-1.5">·</span>contradict {claim.contradict.toFixed(2)}
        </p>
        {ev ? (
          <figure
            onPointerEnter={() => setFocus({ span: { documentId: ev.documentId, text: ev.text } })}
            onPointerLeave={() => setFocus({ span: null })}
            className={clsx(
              "mt-2 border border-line px-2.5 py-2 transition-colors",
              lit ? "border-ring/60 bg-ring-soft" : "bg-surface-2",
            )}
          >
            <blockquote className="text-xs leading-relaxed text-ink-2">“{ev.text}”</blockquote>
            <figcaption className="mt-1.5 flex items-center gap-2 font-mono text-2xs text-ink-3">
              <SourceBadge kind={ev.source} />
              {ev.documentId === currentDocumentId ? (
                <span>this filing · hover to locate</span>
              ) : (
                <Link href={`/filings/${ev.documentId}`} className="truncate text-link hover:underline">
                  {ev.documentTitle}
                </Link>
              )}
            </figcaption>
          </figure>
        ) : (
          <p className="mt-2 border border-dashed border-line-strong px-2.5 py-2 text-xs text-ink-3">
            No source sentence supports this claim. It is shown so the gap is visible.
          </p>
        )}
      </div>
    </li>
  );
}
