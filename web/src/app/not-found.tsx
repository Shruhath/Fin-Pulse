import Link from "next/link";

export default function NotFound() {
  return (
    <main className="flex min-h-dvh items-center justify-center bg-bg px-6">
      <section className="max-w-md text-center">
        <p className="display text-6xl text-brand-ink">404</p>
        <h1 className="display mt-3 text-2xl text-ink">There is nothing at this address</h1>
        <p className="mt-2 text-base text-ink-2">The page may have moved, or the link may be mistyped.</p>
        <div className="mt-6 flex justify-center gap-3">
          <Link href="/home" className="inline-flex h-11 items-center rounded-full bg-brand px-6 text-base font-semibold text-white no-underline hover:bg-brand-hover">
            Go to Home
          </Link>
          <Link href="/" className="inline-flex h-11 items-center rounded-full border border-line-strong px-6 text-base font-medium text-ink no-underline hover:border-brand">
            Start page
          </Link>
        </div>
      </section>
    </main>
  );
}
