"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import clsx from "clsx";

const WINDOWS = [
  { value: "7d", label: "7D", long: "7 days" },
  { value: "30d", label: "30D", long: "30 days" },
  { value: "90d", label: "90D", long: "90 days" },
] as const;

/** Time window shared by every screen through the `w` search param. */
export function WindowControl() {
  const pathname = usePathname();
  const params = useSearchParams();
  const current = params.get("w") ?? "30d";

  return (
    <div role="group" aria-label="Time window" className="flex h-8 items-center rounded-m border border-line bg-surface-2 p-0.5">
      {WINDOWS.map(({ value, label, long }) => {
        const next = new URLSearchParams(params);
        if (value === "30d") next.delete("w");
        else next.set("w", value);
        const qs = next.toString();
        const active = current === value;
        return (
          <Link
            key={value}
            href={qs ? `${pathname}?${qs}` : pathname}
            scroll={false}
            aria-pressed={active}
            aria-label={`Show the last ${long}`}
            className={clsx(
              "flex h-full min-w-10 items-center justify-center rounded-s px-2 text-xs font-semibold no-underline transition-colors",
              active ? "bg-surface text-ink shadow-[0_1px_2px_rgba(12,26,48,0.12)]" : "text-ink-3 hover:text-ink",
            )}
          >
            {label}
          </Link>
        );
      })}
    </div>
  );
}
