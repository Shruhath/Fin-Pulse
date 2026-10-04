import { PlugZap } from "lucide-react";

/** Whole-workspace state when the API cannot be reached. */
export function OfflineState({ message }: { message: string }) {
  return (
    <div className="flex h-full items-center justify-center p-(--gap)">
      <section className="w-full max-w-lg border border-line bg-surface">
        <header className="flex h-8 items-center gap-2 border-b border-line bg-surface-2 px-2.5 font-mono text-2xs">
          <span className="font-semibold text-warn">status</span>
          <span className="text-ink-3">·</span>
          <h1 className="font-medium text-ink-2">no data</h1>
        </header>
        <div className="space-y-3 p-4">
          <PlugZap className="size-5 text-warn" strokeWidth={1.75} aria-hidden="true" />
          <p className="text-base text-ink">{message}</p>
          <p className="text-sm text-ink-2">
            Start the API with <code className="bg-surface-2 px-1.5 py-0.5 font-mono text-xs">make api</code>, or set{" "}
            <code className="bg-surface-2 px-1.5 py-0.5 font-mono text-xs">FINPULSE_PREVIEW=1</code> to work on the
            interface with labelled synthetic data.
          </p>
        </div>
      </section>
    </div>
  );
}

/** Empty state inside a window. */
export function Empty({ children }: { children: React.ReactNode }) {
  return <p className="flex h-full min-h-24 items-center justify-center px-4 py-8 text-center text-sm text-ink-3">{children}</p>;
}

/** A not-found state for a selected record. */
export function Missing({ what }: { what: string }) {
  return <Empty>That {what} is not in the corpus. Pick another from the list.</Empty>;
}
