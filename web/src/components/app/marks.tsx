"use client";

import { useEffect, useRef } from "react";
import clsx from "clsx";

import type { Verification } from "@/lib/api/types";

const META: Record<Verification, { label: string; ink: string; wash: string }> = {
  entailed: { label: "Supported by the source", ink: "text-pos", wash: "bg-pos-weak" },
  contradicted: { label: "Contradicted by the source", ink: "text-neg", wash: "bg-neg-weak" },
  unverified: { label: "Not verified", ink: "text-neu", wash: "bg-neu-weak" },
};

export const VERDICT_LABEL: Record<Verification, string> = {
  entailed: META.entailed.label,
  contradicted: META.contradicted.label,
  unverified: META.unverified.label,
};

/** The pencil mark beside a claim: a tick, a cross or a query, drawn once as it appears. Colour never travels alone. */
export function Tick({ verdict, className, draw = true }: { verdict: Verification; className?: string; draw?: boolean }) {
  const { ink, label } = META[verdict];
  return (
    <svg
      viewBox="0 0 24 24"
      role="img"
      aria-label={label}
      data-draw={draw}
      className={clsx("tick size-5 shrink-0 fill-none stroke-current", ink, className)}
      strokeWidth={2.5}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {verdict === "entailed" && <path pathLength={1} d="M5 12.8 9.8 17.4 19 6.6" />}
      {verdict === "contradicted" && (
        <>
          <path pathLength={1} d="M6.6 6.6 17.4 17.4" />
          <path pathLength={1} d="M17.4 6.6 6.6 17.4" />
        </>
      )}
      {verdict === "unverified" && (
        <>
          <path pathLength={1} d="M9 9.2a3 3 0 1 1 4.4 2.6c-.9.5-1.4 1.1-1.4 2.2" />
          <path pathLength={1} d="M12 18.1v.1" />
        </>
      )}
    </svg>
  );
}

/** The tick on a soft wash, for places where it stands alone. */
export function TickChip({ verdict, className }: { verdict: Verification; className?: string }) {
  return (
    <span className={clsx("inline-flex size-7 shrink-0 items-center justify-center rounded-full", META[verdict].wash, className)}>
      <Tick verdict={verdict} />
    </span>
  );
}

/**
 * Highlighter. The sweep plays when `on` turns true; the text is readable either way.
 * `delay` lets a mark wait for something else (a scroll, a tick) to land first.
 * The sweep is a CSS transition on data-on, flipped on the element itself, so no render is needed to play it.
 */
export function Highlight({ on = true, delay = 0, children, className }: { on?: boolean; delay?: number; children: React.ReactNode; className?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (!on) {
      el.dataset.on = "false";
      return;
    }
    const t = window.setTimeout(() => {
      el.dataset.on = "true";
    }, delay);
    return () => window.clearTimeout(t);
  }, [on, delay]);
  return (
    <span ref={ref} data-on="false" className={clsx("mark-up", className)}>
      {children}
    </span>
  );
}
