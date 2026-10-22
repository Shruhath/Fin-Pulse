import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import clsx from "clsx";

import type { SentimentLabel } from "@/lib/api/types";
import { confidenceStep, fmtPct, fmtScore, NONE } from "@/lib/format";

/** No label means the pipeline has not scored this: shown as such, never as neutral. */
type Maybe = SentimentLabel | null;

const META: Record<SentimentLabel | "unscored", { label: string; icon: typeof Minus; ink: string; wash: string }> = {
  unscored: { label: "Unscored", icon: Minus, ink: "text-ink-3", wash: "bg-surface-2" },
  positive: { label: "Positive", icon: ArrowUpRight, ink: "text-pos", wash: "bg-pos-weak" },
  negative: { label: "Negative", icon: ArrowDownRight, ink: "text-neg", wash: "bg-neg-weak" },
  neutral: { label: "Neutral", icon: Minus, ink: "text-neu", wash: "bg-neu-weak" },
};

/** Icon and colour together, so state survives red/green colour blindness. */
export function SentimentIcon({ sentiment, className }: { sentiment: Maybe; className?: string }) {
  const { icon: Icon, ink, label } = META[sentiment ?? "unscored"];
  return <Icon className={clsx("shrink-0", ink, className ?? "size-4")} strokeWidth={2.4} aria-label={label} role="img" />;
}

export function SentimentPill({ sentiment, score }: { sentiment: Maybe; score?: number | null }) {
  const { label, ink, wash } = META[sentiment ?? "unscored"];
  return (
    <span className={clsx("num inline-flex h-6 items-center gap-1 rounded-full px-2 text-xs font-semibold", wash, ink)}>
      <SentimentIcon sentiment={sentiment} className="size-3.5" />
      <span>{score === undefined ? label : sentiment === null ? NONE : fmtScore(score)}</span>
      {score !== undefined && <span className="sr-only">{label}</span>}
    </span>
  );
}

/** A change over the window: direction glyph and sign travel with the colour. */
export function Delta({ value }: { value: number | null }) {
  if (value === null) return <span className="num text-ink-3">{NONE}</span>;
  const flat = Math.abs(value) < 0.005;
  const tone = flat ? "text-ink-3" : value > 0 ? "text-pos" : "text-neg";
  const Icon = flat ? Minus : value > 0 ? ArrowUpRight : ArrowDownRight;
  return (
    <span className={clsx("num inline-flex items-center gap-0.5 font-semibold", tone)}>
      <Icon className="size-3.5" strokeWidth={2.4} aria-hidden="true" />
      {flat ? "0.00" : fmtScore(value)}
    </span>
  );
}

/** Four segments: coarse on purpose. */
export function Confidence({ value }: { value: number | null }) {
  const step = confidenceStep(value);
  return (
    <span className="inline-flex items-center gap-2" title={value === null ? "No scored mentions" : `Mean calibrated confidence ${fmtPct(value)}`}>
      <span className="flex gap-0.5" aria-hidden="true">
        {[1, 2, 3, 4].map((i) => (
          <span key={i} className={clsx("h-3 w-1.5 rounded-full", i <= step ? "bg-ink-2" : "bg-surface-3")} />
        ))}
      </span>
      <span className="num text-sm text-ink-3">{fmtPct(value)}</span>
    </span>
  );
}
