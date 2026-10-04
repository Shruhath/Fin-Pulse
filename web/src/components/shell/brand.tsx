/** Wordmark: a pulse stroke drawn inside the "F" counter, set beside the name. */
export function BrandMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 28 28" aria-hidden="true" className={className}>
      <rect x="0.5" y="0.5" width="27" height="27" rx="6" fill="var(--shell-accent)" fillOpacity="0.14" stroke="var(--shell-accent)" strokeOpacity="0.45" />
      <path
        d="M4 15.5h5.2l2.1-5.5 3.3 10 2.4-6.6 1.5 2.1H24"
        fill="none"
        stroke="var(--shell-accent)"
        strokeWidth="1.9"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
