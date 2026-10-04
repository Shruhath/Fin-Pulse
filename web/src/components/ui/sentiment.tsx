import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import clsx from "clsx";

import type { SentimentLabel } from "@/lib/api/types";
import { confidenceStep, fmtPct, fmtScore } from "@/lib/format";

const META: Record<SentimentLabel, { label: string; icon: typeof Minus; ink: string; wash: string }> = {
  positive: { label: "Positive", icon: ArrowUpRight, ink: "text-pos", wash: "bg-pos-weak" },
  negative: { label: "Negative", icon: ArrowDownRight, ink: "text-neg", wash: "bg-neg-weak" },
  neutral: { label: "Neutral", icon: Minus, ink: "text-neu", wash: "bg-neu-weak" },
};

/** Icon + colour together, so state survives red/green colour blindness. */
export function SentimentIcon({ sentiment, className }: { sentiment: SentimentLabel; className?: string }) {
  const { icon: Icon, ink, label } = META[sentiment];
  return <Icon className={clsx("shrink-0", ink, className ?? "size-3.5")} strokeWidth={2.25} aria-label={label} role="img" />;
}

export function SentimentPill({ sentiment, score }: { sentiment: SentimentLabel; score?: number }) {
  const { label, ink, wash } = META[sentiment];
  return (
    <span className={clsx("inline-flex h-6 items-center gap-1 rounded-s px-1.5 text-xs font-semibold", wash, ink)}>
      <SentimentIcon sentiment={sentiment} />
      <span>{score === undefined ? label : fmtScore(score)}</span>
      {score !== undefined && <span className="sr-only">{label}</span>}
    </span>
  );
}

export function Delta({ value }: { value: number }) {
  const flat = Math.abs(value) < 0.005;
  const tone = flat ? "text-ink-3" : value > 0 ? "text-pos" : "text-neg";
  return <span className={clsx("num font-medium", tone)}>{flat ? "0.00" : fmtScore(value)}</span>;
}

/** Four segments: coarse on purpose. */
export function Confidence({ value }: { value: number }) {
  const step = confidenceStep(value);
  return (
    <span className="inline-flex items-center gap-2" title={`Mean calibrated confidence ${fmtPct(value)}`}>
      <span className="flex gap-0.5" aria-hidden="true">
        {[1, 2, 3, 4].map((i) => (
          <span key={i} className={clsx("h-2.5 w-1.5 rounded-[1px]", i <= step ? "bg-ink-2" : "bg-surface-3")} />
        ))}
      </span>
      <span className="num text-xs text-ink-3">{fmtPct(value)}</span>
    </span>
  );
}
