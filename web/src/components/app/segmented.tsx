"use client";

import Link from "next/link";
import clsx from "clsx";

import { useSlider } from "./use-slider";

export interface SegmentItem<V extends string> {
  value: V;
  label: React.ReactNode;
  /** When set the segment is a link (used for URL state such as the time window). */
  href?: string;
  count?: number;
}

/** A pill control with a thumb that slides between options. Buttons by default, links when items carry an href. */
export function Segmented<V extends string>({
  items,
  value,
  onChange,
  label,
  className,
}: {
  items: SegmentItem<V>[];
  value: V;
  onChange?: (v: V) => void;
  label: string;
  className?: string;
}) {
  const [ref, box] = useSlider<HTMLDivElement>([value, items.length]);
  return (
    <div
      ref={ref}
      role="group"
      aria-label={label}
      className={clsx("relative inline-flex rounded-full border border-line bg-surface-2 p-0.5", className)}
    >
      {box && (
        <span
          aria-hidden="true"
          className="absolute top-0.5 left-0 rounded-full bg-surface shadow-1 transition-[transform,width] duration-300 ease-(--ease-out)"
          style={{ width: box.w, height: box.h, transform: `translateX(${box.x}px)` }}
        />
      )}
      {items.map((it) => {
        const on = it.value === value;
        const cls = clsx(
          "relative z-[1] inline-flex h-8 items-center gap-1.5 rounded-full px-3.5 text-sm font-medium whitespace-nowrap no-underline transition-colors duration-200",
          on ? "text-ink" : "text-ink-3 hover:text-ink",
          !box && on && "bg-surface shadow-1",
        );
        const content = (
          <>
            {it.label}
            {it.count !== undefined && <span className="num text-xs text-ink-3">{it.count}</span>}
          </>
        );
        return it.href ? (
          <Link key={it.value} href={it.href} scroll={false} data-active={on} aria-current={on ? "true" : undefined} className={cls}>
            {content}
          </Link>
        ) : (
          <button key={it.value} type="button" data-active={on} aria-pressed={on} onClick={() => onChange?.(it.value)} className={cls}>
            {content}
          </button>
        );
      })}
    </div>
  );
}
