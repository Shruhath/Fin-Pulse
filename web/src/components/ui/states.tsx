import { FileSearch, PlugZap } from "lucide-react";

/** Whole-page state when the API cannot be reached. */
export function OfflineState({ message }: { message: string }) {
  return (
    <div className="mx-auto flex max-w-lg flex-col items-center py-20 text-center">
      <span className="flex size-14 items-center justify-center rounded-2xl bg-warn-weak text-warn">
        <PlugZap className="size-7" strokeWidth={1.75} aria-hidden="true" />
      </span>
      <h1 className="display mt-5 text-xl text-ink">Nothing to show yet</h1>
      <p className="mt-2 text-base text-ink-2">{message}</p>
      <p className="mt-4 text-sm text-ink-3">
        Start the API with <code className="rounded-md bg-surface-2 px-1.5 py-0.5 font-mono text-xs">make live</code>, or run{" "}
        <code className="rounded-md bg-surface-2 px-1.5 py-0.5 font-mono text-xs">scripts/live.sh preview</code> to look around on clearly labelled
        synthetic data.
      </p>
    </div>
  );
}

/** Empty state inside a section. Says what would fill it. */
export function Empty({ children, icon = true }: { children: React.ReactNode; icon?: boolean }) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-2xl border border-dashed border-line-strong px-6 py-10 text-center text-sm text-ink-3">
      {icon && <FileSearch className="size-6 text-ink-3/70" strokeWidth={1.6} aria-hidden="true" />}
      <p className="max-w-[46ch]">{children}</p>
    </div>
  );
}

/** A not-found state for a selected record. */
export function Missing({ what }: { what: string }) {
  return <Empty>That {what} is not in the corpus. Pick another from the list.</Empty>;
}
