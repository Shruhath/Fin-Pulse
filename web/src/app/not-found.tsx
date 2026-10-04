import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex h-full items-center justify-center p-(--gap)">
      <section className="w-full max-w-md border border-line bg-surface">
        <header className="flex h-8 items-center gap-2 border-b border-line bg-surface-2 px-2.5 font-mono text-2xs">
          <span className="font-semibold text-warn">404</span>
          <span className="text-ink-3">·</span>
          <h1 className="font-medium text-ink-2">no such window</h1>
        </header>
        <div className="space-y-2 p-4 text-sm text-ink-2">
          <p>Nothing lives at this address.</p>
          <p>
            Press <kbd className="border border-line bg-surface-2 px-1 text-xs">1</kbd> for the overview, or{" "}
            <Link href="/" className="text-link hover:underline">
              go there now
            </Link>
            .
          </p>
        </div>
      </section>
    </div>
  );
}
