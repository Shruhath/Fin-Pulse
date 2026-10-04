import { PlugZap } from "lucide-react";

export function OfflineState({ message }: { message: string }) {
  return (
    <div className="mx-auto flex max-w-xl flex-col items-start gap-3 px-6 py-24">
      <PlugZap className="size-6 text-warn" strokeWidth={1.75} aria-hidden="true" />
      <h1 className="text-lg font-semibold text-ink">No data to show yet</h1>
      <p className="text-base text-ink-2">{message}</p>
      <p className="text-base text-ink-2">
        Start the API with <code className="rounded-s bg-surface-2 px-1.5 py-0.5 font-mono text-sm">make api</code>, or set{" "}
        <code className="rounded-s bg-surface-2 px-1.5 py-0.5 font-mono text-sm">FINPULSE_PREVIEW=1</code> to work on the
        interface with labelled synthetic data.
      </p>
    </div>
  );
}

export function EmptyRow({ children }: { children: React.ReactNode }) {
  return <p className="px-4 py-10 text-center text-sm text-ink-3">{children}</p>;
}
