import { Mic } from "lucide-react";

import { Tick } from "@/components/app/marks";
import { SentimentIcon, SentimentPill } from "@/components/ui/sentiment";
import { SourceBadge } from "@/components/ui/source-badge";

/*
 * Small illustrative specimens for the start page. They are built from the real components with invented
 * names so the page can show what each part of the app does without republishing a real filing.
 */

const frame = "rounded-3xl border border-line bg-surface p-5 shadow-2 sm:p-6";
const label = (
  <p className="mb-4 text-xs font-medium text-ink-3">
    <span className="rounded-full bg-surface-3 px-2.5 py-0.5">Illustrative</span>
  </p>
);

export function AskSpecimen() {
  return (
    <div className={frame} role="img" aria-label="An example question with two claims, one supported and one not verified">
      {label}
      <p className="text-md leading-6 font-semibold text-ink">What action did SEBI take against Sample Bank Limited?</p>
      <ul className="mt-4 divide-y divide-line">
        <li className="flex gap-3 py-3">
          <Tick verdict="entailed" className="mt-0.5 size-6" draw={false} />
          <div>
            <p className="text-base text-ink">SEBI imposed a penalty of ₹25 lakh on Sample Bank Limited for delayed disclosures.</p>
            <p className="mt-1 text-sm text-pos">Supported by the source</p>
          </div>
        </li>
        <li className="flex gap-3 py-3">
          <Tick verdict="unverified" className="mt-0.5 size-6" draw={false} />
          <div>
            <p className="text-base text-ink">The bank must also appoint a new compliance officer.</p>
            <p className="mt-1 text-sm text-neu">Not verified: no sentence supports it</p>
          </div>
        </li>
      </ul>
      <div className="mt-2 flex items-center gap-2 rounded-2xl border border-line bg-surface-2 py-2 pr-2 pl-4 text-sm text-ink-3">
        <span className="flex-1">Ask a question, or press the microphone</span>
        <span className="inline-flex size-9 items-center justify-center rounded-full bg-surface text-ink-2 shadow-1">
          <Mic className="size-4" aria-hidden="true" />
        </span>
      </div>
    </div>
  );
}

export function CompanySpecimen() {
  return (
    <div className={frame} role="img" aria-label="One paragraph that is good news for one company and bad news for another">
      {label}
      <p className="text-[1.0625rem] leading-8 text-ink-2">
        <mark className="rounded-[5px] underline decoration-pos decoration-2 underline-offset-4 bg-pos-weak px-0.5 font-medium text-ink">
          Sample Bank Limited
          <SentimentIcon sentiment="positive" className="ml-0.5 inline size-3.5 -translate-y-px" />
        </mark>{" "}
        reported a rise in net profit, while{" "}
        <mark className="rounded-[5px] underline decoration-neg decoration-2 underline-offset-4 bg-neg-weak px-0.5 font-medium text-ink">
          Example Finance Limited
          <SentimentIcon sentiment="negative" className="ml-0.5 inline size-3.5 -translate-y-px" />
        </mark>{" "}
        was admitted to insolvency proceedings in the same week.
      </p>
      <ul className="mt-5 space-y-2 border-t border-line pt-4">
        {[
          ["Sample Bank Limited", "positive", 0.62],
          ["Example Finance Limited", "negative", -0.71],
        ].map(([name, s, score]) => (
          <li key={name as string} className="flex items-center justify-between gap-3 text-base">
            <span className="font-medium text-ink">{name}</span>
            <SentimentPill sentiment={s as "positive" | "negative"} score={score as number} />
          </li>
        ))}
      </ul>
    </div>
  );
}

export function EventSpecimen() {
  return (
    <div className={frame} role="img" aria-label="An example event record pulled out of a filing">
      {label}
      <div className="flex flex-wrap items-center gap-2">
        <span className="inline-flex h-6 items-center rounded-full bg-brand px-2.5 text-xs font-semibold text-white">SEBI Penalty</span>
        <SourceBadge kind="SEBI" />
        <span className="ml-auto">
          <SentimentPill sentiment="negative" />
        </span>
      </div>
      <p className="mt-3 text-md font-semibold text-ink">Example Industries Limited</p>
      <p className="mt-1 text-base text-ink-2">Penalty imposed for creating a false appearance of trading.</p>
      <dl className="mt-4 grid grid-cols-[minmax(0,8rem)_1fr] gap-x-4 gap-y-2 rounded-xl bg-surface-2 p-4 text-sm">
        <dt className="text-ink-3">Amount</dt>
        <dd className="text-ink">₹10,00,000</dd>
        <dt className="text-ink-3">Section</dt>
        <dd className="text-ink">15HA, SEBI Act</dd>
        <dt className="text-ink-3">Pay within</dt>
        <dd className="text-ink">45 days</dd>
      </dl>
    </div>
  );
}
