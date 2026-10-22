import Link from "next/link";
import { ChevronLeft } from "lucide-react";

/** One title, one sentence of what the page is for, and the controls that scope it. */
export function PageHeader({
  title,
  description,
  actions,
  back,
}: {
  title: React.ReactNode;
  description?: React.ReactNode;
  actions?: React.ReactNode;
  back?: { href: string; label: string };
}) {
  return (
    <header className="mb-7">
      {back && (
        <Link href={back.href} className="-ml-1 mb-3 inline-flex items-center gap-0.5 rounded-full py-1 pr-2 pl-1 text-sm font-medium text-ink-3 no-underline transition-colors hover:text-ink">
          <ChevronLeft className="size-4" aria-hidden="true" />
          {back.label}
        </Link>
      )}
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
        <div className="min-w-0">
          <h1 className="display text-[2rem] leading-[2.4rem] text-ink">{title}</h1>
          {description && <p className="mt-1.5 max-w-[62ch] text-base text-ink-2">{description}</p>}
        </div>
        {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
      </div>
    </header>
  );
}

/** A titled block on a page: a heading, an optional aside, and the content. */
export function Section({
  title,
  aside,
  children,
  className,
}: {
  title: React.ReactNode;
  aside?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={className}>
      <div className="mb-3 flex items-baseline justify-between gap-4">
        <h2 className="text-lg font-semibold text-ink">{title}</h2>
        {aside && <div className="text-sm text-ink-3">{aside}</div>}
      </div>
      {children}
    </section>
  );
}
