import clsx from "clsx";

/** Flat, hairline-bordered work area. Panels never nest. */
export function Panel({
  title,
  meta,
  children,
  className,
  bodyClassName,
  id,
}: {
  title: string;
  meta?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  bodyClassName?: string;
  id?: string;
}) {
  const headingId = id ? `${id}-title` : undefined;
  return (
    <section aria-labelledby={headingId} className={clsx("flex min-w-0 flex-col rounded-l border border-line bg-surface", className)}>
      <header className="flex min-h-12 flex-wrap items-center gap-x-4 gap-y-1 border-b border-line px-4 py-2.5">
        <h2 id={headingId} className="text-sm font-semibold text-ink">
          {title}
        </h2>
        {meta && <div className="ml-auto flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-ink-3">{meta}</div>}
      </header>
      <div className={clsx("min-h-0 flex-1", bodyClassName)}>{children}</div>
    </section>
  );
}
