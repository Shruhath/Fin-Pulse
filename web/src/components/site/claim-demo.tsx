"use client";

import { useState } from "react";

import { Segmented } from "@/components/app/segmented";
import { Highlight, Tick, VERDICT_LABEL } from "@/components/app/marks";
import type { Verification } from "@/lib/api/types";

/* An invented order about an invented company, labelled as such: the landing page shows how a claim is checked without republishing a real order. */
const CASES: Record<Verification, { claim: string; note: string }> = {
  entailed: {
    claim: "SEBI fined Example Industries Limited ₹10 lakh.",
    note: "The order says so in the sentence marked above.",
  },
  contradicted: {
    claim: "SEBI fined Example Industries Limited ₹1 crore.",
    note: "The order gives ₹10,00,000, which is ₹10 lakh. The mismatch is shown, not hidden.",
  },
  unverified: {
    claim: "Example Industries Limited was also barred from the market for a year.",
    note: "No sentence in the order supports this, so it is flagged instead of asserted.",
  },
};

const TONE: Record<Verification, string> = { entailed: "text-pos", contradicted: "text-neg", unverified: "text-neu" };

/** A claim checked against its source, in three outcomes. The tick draws itself each time the outcome changes. */
export function ClaimDemo() {
  const [v, setV] = useState<Verification>("entailed");
  const c = CASES[v];
  return (
    <figure className="rounded-3xl bg-surface p-5 text-ink shadow-pop sm:p-7" aria-label="Example of a claim checked against a source sentence">
      <figcaption className="mb-4 flex flex-wrap items-center justify-between gap-2 text-sm text-ink-3">
        <span className="font-medium text-ink-2">SEBI adjudication order</span>
        <span className="rounded-full bg-surface-3 px-2.5 py-0.5 text-xs font-medium">Illustrative example, not a real order</span>
      </figcaption>
      <p className="text-[1.0625rem] leading-8 text-ink-2">
        On examining the trading pattern, it was observed that the Noticee had placed orders that created a false appearance of trading in the scrip.{" "}
        <Highlight on={v !== "unverified"} key={v}>
          Accordingly, a penalty of ₹10,00,000 is imposed on Example Industries Limited under Section 15HA of the SEBI Act.
        </Highlight>{" "}
        The Noticee shall pay the penalty within forty-five days of receipt of this order.
      </p>

      <div className="mt-6 rounded-2xl bg-surface-2 p-5">
        <p className="text-sm font-medium text-ink-3">A claim made about it</p>
        <div className="mt-2 flex items-start gap-3">
          <span key={v} className="mt-0.5">
            <Tick verdict={v} className="size-7" />
          </span>
          <div>
            <p className="text-md leading-6 font-medium text-ink">{c.claim}</p>
            <p className={`mt-1 text-sm font-semibold ${TONE[v]}`}>{VERDICT_LABEL[v]}</p>
            <p className="mt-1 text-sm text-ink-3">{c.note}</p>
          </div>
        </div>
      </div>

      <div className="mt-5 max-w-full overflow-x-auto">
        <Segmented
          label="Try an outcome"
          value={v}
          onChange={setV}
          items={[
            { value: "entailed", label: "Supported" },
            { value: "contradicted", label: "Contradicted" },
            { value: "unverified", label: "Not verified" },
          ]}
        />
      </div>
    </figure>
  );
}
