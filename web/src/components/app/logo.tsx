import clsx from "clsx";

/** A highlighter stroke with a pencil tick on it: the product in one mark. */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 28 28" aria-hidden="true" className={clsx("size-7 shrink-0", className)}>
      <rect x="1.5" y="7.5" width="25" height="14" rx="4.5" fill="var(--hl-solid, #ffe95e)" transform="rotate(-6 14 14.5)" />
      <path d="M8 15.2 12.2 19.4 20.4 9.6" fill="none" stroke="#162a86" strokeWidth="2.7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function Wordmark({ className }: { className?: string }) {
  return (
    <span className={clsx("display text-[1.3rem] leading-none", className)} style={{ letterSpacing: "-0.03em" }}>
      FinPulse
    </span>
  );
}
