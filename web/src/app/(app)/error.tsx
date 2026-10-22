"use client";

import Link from "next/link";
import { TriangleAlert } from "lucide-react";

/** A page that failed to load keeps the frame, says what happened and offers a way forward. */
export default function Error({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div className="mx-auto flex max-w-lg flex-col items-center py-20 text-center">
      <span className="flex size-14 items-center justify-center rounded-2xl bg-neg-weak text-neg">
        <TriangleAlert className="size-7" strokeWidth={1.75} aria-hidden="true" />
      </span>
      <h1 className="display mt-5 text-xl text-ink">This page could not be loaded</h1>
      <p className="mt-2 text-base text-ink-2">
        Something went wrong while loading it. The most common cause is that the API is not running; start it with{" "}
        <code className="rounded-md bg-surface-2 px-1.5 py-0.5 font-mono text-sm">make live</code>.
      </p>
      {error.digest && <p className="num mt-2 text-xs text-ink-3">Reference {error.digest}</p>}
      <div className="mt-6 flex gap-3">
        <button
          type="button"
          onClick={reset}
          className="inline-flex h-11 items-center rounded-full bg-brand px-6 text-base font-semibold text-white transition-colors hover:bg-brand-hover"
        >
          Try again
        </button>
        <Link href="/home" className="inline-flex h-11 items-center rounded-full border border-line-strong px-6 text-base font-medium text-ink no-underline hover:border-brand">
          Go to Home
        </Link>
      </div>
    </div>
  );
}
