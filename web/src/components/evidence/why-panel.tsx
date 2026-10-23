"use client";

import { useEffect, useState } from "react";
import clsx from "clsx";

import { SentimentPill } from "@/components/ui/sentiment";
import { Empty } from "@/components/ui/states";
import type { EntitySpan, Explanation } from "@/lib/api/types";
import { fmtPct } from "@/lib/format";

const API = process.env.NEXT_PUBLIC_FINPULSE_API_URL ?? "http://127.0.0.1:8000";

export interface WhyTarget {
  documentId: string;
  span: EntitySpan;
}

/**
 * Why the model scored a company the way it did. The words in the window the model read are shaded by how
 * much each one pushed the predicted label up (solid underline) or down (dotted underline), measured with
 * Integrated Gradients; shade and line style both carry it, never colour alone.
 */
export function WhyPanel({ target }: { target: WhyTarget | null }) {
  const [state, setState] = useState<{ key: string; data?: Explanation; error?: string }>({ key: "" });
  const key = target ? `${target.documentId}:${target.span.start}:${target.span.end}` : "";

  useEffect(() => {
    if (!target) return;
    let live = true;
    const url = `${API}/api/documents/${target.documentId}/explain?start=${target.span.start}&end=${target.span.end}`;
    fetch(url, { cache: "no-store" })
      .then(async (res) => {
        if (!res.ok) throw new Error(res.status === 409 ? "Explanations need the fine-tuned FinBERT, which is not loaded here." : `The API answered ${res.status}.`);
        return (await res.json()) as Explanation;
      })
      .then((data) => live && setState({ key, data }))
      .catch((e: Error) => live && setState({ key, error: e.message }));
    return () => {
      live = false;
    };
    // the key identifies the request; target changes identity with every parent render
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  if (!target) return <Empty>Click a company in the text to see which words drove its score.</Empty>;
  if (state.key !== key) return <p className="px-1 text-sm text-ink-3" role="status">Reading the sentence the way the model did…</p>;
  if (state.error || !state.data) return <Empty>{state.error ?? "No explanation came back."}</Empty>;

  const { label, probabilities, words, steps, convergence, model } = state.data;
  const top = [...words].filter((w) => !w.entity).sort((a, b) => Math.abs(b.weight) - Math.abs(a.weight)).slice(0, 6);
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <p className="text-base font-semibold text-ink">{target.span.surface}</p>
        <SentimentPill sentiment={label} />
        <span className="num text-sm text-ink-3">{fmtPct(probabilities[label])} sure</span>
      </div>
      <p className="text-sm leading-6 text-ink-2">
        The words around the company, shaded by how much each pushed the score toward <strong className="font-semibold">{label}</strong> (solid
        underline) or away from it (dotted underline).
      </p>
      <p className="text-[0.95rem] leading-8 text-ink-2" aria-label="The text the model read, with each word's influence">
        {words.map((w, i) => {
          const strength = Math.abs(w.weight);
          const shade = strength < 0.08 ? 0 : Math.min(0.85, 0.12 + strength * 0.7);
          return (
            <span key={i}>
              <span
                title={`${w.weight > 0 ? "toward" : "away from"} ${label}: ${Math.round(w.weight * 100)}`}
                style={shade ? { backgroundColor: `color-mix(in oklab, var(${w.weight > 0 ? "--brand" : "--ink-3"}) ${Math.round(shade * 100)}%, transparent)` } : undefined}
                className={clsx(
                  "rounded-[4px] px-0.5",
                  w.entity && "font-semibold text-ink",
                  shade > 0 && (w.weight > 0 ? "underline decoration-brand decoration-2 underline-offset-4" : "underline decoration-dotted decoration-ink-3 decoration-2 underline-offset-4"),
                  shade > 0.5 && w.weight > 0 && "text-white",
                )}
              >
                {w.text}
              </span>{" "}
            </span>
          );
        })}
      </p>
      {top.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-ink">Biggest influences</h3>
          <ul className="mt-2 flex flex-wrap gap-2">
            {top.map((w, i) => (
              <li key={i} className="num rounded-full bg-surface-2 px-2.5 py-1 text-sm text-ink-2">
                {w.text} <span className="text-ink-3">{w.weight > 0 ? "+" : "−"}{Math.round(Math.abs(w.weight) * 100)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      <p className="text-xs leading-5 text-ink-3">
        Integrated Gradients, {steps} steps, from a baseline of blank words. The influences add up to the model&apos;s score
        for this label within {fmtPct(convergence)}. Model: {model ?? "unknown"}.
      </p>
    </div>
  );
}
