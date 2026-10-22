import Link from "next/link";
import { ArrowRight } from "lucide-react";

import { Highlight } from "@/components/app/marks";
import { LogoMark, Wordmark } from "@/components/app/logo";
import { ThemeToggle } from "@/components/app/theme-toggle";
import { ClaimDemo } from "@/components/site/claim-demo";
import { SentimentResults, sentimentPairs } from "@/components/site/results";
import { AskSpecimen, CompanySpecimen, EventSpecimen } from "@/components/site/specimens";
import { getEval, getStatus, isPreview } from "@/lib/api/client";
import { fmtInt } from "@/lib/format";

const STEPS = [
  { name: "Read", text: "Pulls the text out of the PDF, using OCR on scanned pages." },
  { name: "Find the companies", text: "Recognises each company and links it to the listed one." },
  { name: "Score each one", text: "Gives every company its own sentiment, not one score for the whole article." },
  { name: "Pick out events", text: "Turns penalties, admissions and dividends into structured records." },
  { name: "Check the claims", text: "Writes a summary, then checks each claim against the sentence it cites." },
];

const NOT_YET = [
  "Human-labelled passages do not exist yet, so how many companies and events the system misses is not measured.",
  "Models trained on news headlines read most regulatory text as neutral. Treat sentiment on orders as a finding about that gap, not as a signal.",
  "Spoken questions were tested on synthetic speech only.",
];

const cta =
  "inline-flex h-12 items-center gap-2 rounded-full bg-white px-7 text-base font-semibold text-rail no-underline transition-[transform,box-shadow] duration-200 hover:-translate-y-0.5 hover:shadow-2 active:translate-y-0";

// The figures on this page come from the API when it loads, so it is never built ahead of time.
export const dynamic = "force-dynamic";

export default async function LandingPage() {
  const [status, report] = await Promise.all([getStatus(), getEval()]);
  const corpus = status.state === "ok" ? status.data : null;
  const preview = isPreview();
  const evalReport = report.state === "ok" ? report.data : null;
  const pairs = evalReport && !preview ? sentimentPairs(evalReport) : [];

  return (
    <div className="bg-bg">
      {/* First viewport: the idea, one action, and the mechanism working. */}
      <section className="relative overflow-hidden bg-rail text-white">
        <header className="mx-auto flex h-20 max-w-[1180px] items-center justify-between px-5 sm:px-8">
          <Link href="/" className="flex items-center gap-2.5 text-white no-underline" aria-label="FinPulse">
            <LogoMark />
            <Wordmark />
          </Link>
          <nav aria-label="Page" className="hidden items-center gap-8 text-sm font-medium text-rail-ink md:flex">
            <a href="#how" className="no-underline transition-colors hover:text-white">
              How it works
            </a>
            <a href="#results" className="no-underline transition-colors hover:text-white">
              Results
            </a>
            <Link href="/method" className="no-underline transition-colors hover:text-white">
              Method
            </Link>
          </nav>
          <div className="flex items-center gap-1">
            <ThemeToggle label={false} className="text-rail-ink hover:bg-white/10 hover:text-white" />
            <Link
              href="/home"
              className="inline-flex h-10 items-center rounded-full bg-white/12 px-5 text-sm font-semibold text-white no-underline transition-colors hover:bg-white/20"
            >
              Open the app
            </Link>
          </div>
        </header>

        <div className="mx-auto grid max-w-[1180px] items-center gap-14 px-5 pt-10 pb-20 sm:px-8 lg:grid-cols-[1fr_minmax(0,34rem)] lg:pt-16 lg:pb-28">
          <div>
            <h1 className="display text-[clamp(2.75rem,6.4vw,4.6rem)] leading-[1.03] tracking-[-0.03em]">
              Read the market{" "}
              <Highlight on delay={450} className="[--hl:#ffffff] [--hl-ink:var(--rail)]">
                before it moves.
              </Highlight>
            </h1>
            <p className="mt-6 max-w-[50ch] text-lg leading-8 text-rail-ink">
              FinPulse reads Indian regulatory filings, scores sentiment for each company, pulls out the events, and checks every claim against the
              sentence that supports it. Nothing is asserted without evidence.
            </p>
            <div className="mt-9 flex flex-wrap items-center gap-x-6 gap-y-4">
              <Link href="/home" className={cta}>
                Open the app <ArrowRight className="size-5" aria-hidden="true" />
              </Link>
              <a href="#how" className="text-base font-medium text-white underline decoration-white/40 underline-offset-4 transition-colors hover:decoration-white">
                See how it works
              </a>
            </div>
            <p className="mt-10 max-w-[52ch] text-sm leading-6 text-rail-ink/85">
              {corpus && !preview ? (
                <>
                  <span className="num font-semibold text-white">{fmtInt(corpus.documents)}</span> SEBI, NCLT and RBI filings read so far.{" "}
                </>
              ) : null}
              Every model runs on your own computer. Nothing is sent to a hosted service.
            </p>
          </div>
          <ClaimDemo />
        </div>
      </section>

      <section id="how" className="scroll-mt-6 border-b border-line">
        <div className="mx-auto max-w-[1180px] px-5 py-20 sm:px-8 lg:py-28">
          <h2 className="display max-w-[22ch] text-[clamp(1.9rem,4vw,2.75rem)] leading-[1.1] text-ink">From a forty-page order to claims you can check</h2>
          <ol className="relative mt-14 grid gap-10 md:grid-cols-5 md:gap-6">
            <span className="absolute top-4 right-[10%] left-[10%] hidden h-0.5 rounded-full bg-line md:block" aria-hidden="true" />
            {STEPS.map((s, i) => (
              <li key={s.name} className="relative flex gap-5 md:block">
                <span className="relative z-[1] flex size-8 shrink-0 items-center justify-center rounded-full bg-brand text-sm font-bold text-white md:mx-auto">{i + 1}</span>
                <div className="md:mt-4 md:text-center">
                  <h3 className="text-md font-semibold text-ink">{s.name}</h3>
                  <p className="mt-1 text-base leading-6 text-ink-2">{s.text}</p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="border-b border-line">
        <div className="mx-auto max-w-[1180px] space-y-24 px-5 py-20 sm:px-8 lg:space-y-32 lg:py-28">
          <Feature
            title="Ask a question and get an answer you can check"
            body="Type it or say it. Each claim in the answer cites a sentence from a filing, and a second model checks the claim against that sentence. If the filings do not answer, FinPulse says so instead of guessing."
            href="/ask"
            action="Open Ask"
          >
            <AskSpecimen />
          </Feature>
          <Feature
            flip
            title="Sentiment for each company, not each article"
            body="One paragraph can be good news for one company and bad news for another. FinPulse scores every mention on its own, then shows how each company reads over time."
            href="/companies"
            action="See the companies"
          >
            <CompanySpecimen />
          </Feature>
          <Feature
            title="Events pulled out and traced back"
            body="Penalties, insolvency admissions, dividends and auditor changes become structured records. Each one opens the filing at the sentence that triggered it."
            href="/events"
            action="Browse events"
          >
            <EventSpecimen />
          </Feature>
        </div>
      </section>

      <section id="results" className="scroll-mt-6 border-b border-line">
        <div className="mx-auto grid max-w-[1180px] gap-14 px-5 py-20 sm:px-8 lg:grid-cols-[1fr_1fr] lg:py-28">
          <div>
            <h2 className="display text-[clamp(1.9rem,4vw,2.75rem)] leading-[1.1] text-ink">Measured, not claimed</h2>
            <p className="mt-4 max-w-[48ch] text-base leading-7 text-ink-2">
              {pairs.length > 0
                ? "Macro-F1 on the held-out test split of each public dataset, for FinPulse's model and for the simpler baseline it replaces. Higher is better. These figures are read from the evaluation harness when this page loads."
                : "Every stage is compared with a simpler baseline on public benchmarks and on Indian data. The figures appear here when the evaluation has run."}
            </p>
            <Link href="/evaluation" className="mt-6 inline-flex items-center gap-1.5 text-base font-semibold text-brand-ink no-underline hover:underline">
              All results <ArrowRight className="size-4" aria-hidden="true" />
            </Link>
          </div>
          <div>
            {pairs.length > 0 && evalReport && <SentimentResults report={evalReport} />}
            <div className={pairs.length > 0 ? "mt-10 border-t border-line pt-8" : ""}>
              <h3 className="text-base font-semibold text-ink">What is not measured yet</h3>
              <ul className="mt-3 list-disc space-y-2 pl-5 text-base leading-7 text-ink-2 marker:text-ink-3">
                {NOT_YET.map((t) => (
                  <li key={t}>{t}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </section>

      <section className="bg-rail text-white">
        <div className="mx-auto flex max-w-[1180px] flex-col items-start gap-8 px-5 py-20 sm:px-8 lg:flex-row lg:items-center lg:justify-between lg:py-24">
          <div>
            <h2 className="display text-[clamp(1.9rem,4vw,2.75rem)] leading-[1.1]">Ask your first question</h2>
            <p className="mt-3 max-w-[48ch] text-lg text-rail-ink">Start with a company you follow. The answer shows its sources.</p>
          </div>
          <Link href="/home" className={cta}>
            Open the app <ArrowRight className="size-5" aria-hidden="true" />
          </Link>
        </div>
        <footer className="border-t border-white/12">
          <div className="mx-auto flex max-w-[1180px] flex-wrap items-center justify-between gap-x-8 gap-y-3 px-5 py-6 text-sm text-rail-ink sm:px-8">
            <p>Team 6 · 23CSE471 Natural Language Processing · Amrita School of Computing</p>
            <p className="flex flex-wrap gap-x-6 gap-y-1">
              <Link href="/method" className="no-underline hover:text-white">
                Method
              </Link>
              <Link href="/evaluation" className="no-underline hover:text-white">
                Evaluation
              </Link>
              <a href="https://github.com/Shruhath/Fin-Pulse" className="no-underline hover:text-white">
                Source code
              </a>
              <span>Research software, not investment advice.</span>
            </p>
          </div>
        </footer>
      </section>
    </div>
  );
}

function Feature({
  title,
  body,
  href,
  action,
  flip = false,
  children,
}: {
  title: string;
  body: string;
  href: string;
  action: string;
  flip?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="grid items-center gap-10 lg:grid-cols-2 lg:gap-20">
      <div className={flip ? "lg:order-2" : undefined}>
        <h3 className="display text-[clamp(1.6rem,3.2vw,2.25rem)] leading-[1.15] text-ink">{title}</h3>
        <p className="mt-4 max-w-[46ch] text-base leading-7 text-ink-2">{body}</p>
        <Link href={href} className="mt-6 inline-flex items-center gap-1.5 text-base font-semibold text-brand-ink no-underline hover:underline">
          {action} <ArrowRight className="size-4" aria-hidden="true" />
        </Link>
      </div>
      <div className={flip ? "lg:order-1" : undefined}>{children}</div>
    </div>
  );
}
