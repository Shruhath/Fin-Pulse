"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowUp, Sparkles } from "lucide-react";

/** The shortcut to the one thing most visitors came to do. Hands the question to the Ask page. */
export function AskBar({ suggestions }: { suggestions: string[] }) {
  const router = useRouter();
  const [q, setQ] = useState("");
  const ok = q.trim().length >= 3;
  return (
    <div>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (ok) router.push(`/ask?q=${encodeURIComponent(q.trim())}`);
        }}
        className="group relative"
      >
        <Sparkles className="pointer-events-none absolute top-1/2 left-5 size-5 -translate-y-1/2 text-brand-ink" aria-hidden="true" />
        <label htmlFor="home-ask" className="sr-only">
          Ask the filings a question
        </label>
        <input
          id="home-ask"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          maxLength={500}
          placeholder="Ask the filings a question"
          className="h-16 w-full rounded-2xl border border-line bg-surface pr-16 pl-14 text-md text-ink shadow-2 outline-none transition-shadow duration-200 focus:border-brand focus:shadow-[0_0_0_4px_var(--brand-weak)]"
        />
        <button
          type="submit"
          disabled={!ok}
          aria-label="Ask"
          className="absolute top-1/2 right-3 inline-flex size-10 -translate-y-1/2 items-center justify-center rounded-xl bg-brand text-white transition-[background-color,transform,opacity] duration-150 hover:bg-brand-hover active:scale-95 disabled:opacity-35"
        >
          <ArrowUp className="size-5" aria-hidden="true" />
        </button>
      </form>
      {suggestions.length > 0 && (
        <ul className="mt-3 flex flex-wrap gap-2">
          {suggestions.slice(0, 2).map((s) => (
            <li key={s} className="max-w-full">
              <Link
                href={`/ask?q=${encodeURIComponent(s)}`}
                className="inline-flex max-w-full min-w-0 rounded-full border border-line bg-surface px-3.5 py-1.5 text-sm text-ink-2 no-underline transition-colors hover:border-brand hover:text-ink"
              >
                <span className="truncate">{s}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
