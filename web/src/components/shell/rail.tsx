"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";

import { BrandMark } from "./brand";
import { NAV, isActive } from "./nav";
import { ThemeToggle } from "./theme-toggle";

export function RailNav({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  return (
    <nav aria-label="Primary" className="flex flex-col gap-0.5">
      {NAV.map(({ href, label, icon: Icon }) => {
        const active = isActive(pathname, href);
        return (
          <Link
            key={href}
            href={href}
            onClick={onNavigate}
            aria-current={active ? "page" : undefined}
            className={clsx(
              "group relative flex h-9 items-center gap-3 rounded-m px-3 text-sm font-medium no-underline transition-colors",
              active
                ? "bg-shell-2 text-shell-ink-strong"
                : "text-shell-ink hover:bg-shell-2/60 hover:text-shell-ink-strong",
            )}
          >
            <span
              aria-hidden="true"
              className={clsx(
                "absolute inset-y-2 left-0 w-px rounded-full transition-opacity",
                active ? "bg-shell-accent opacity-100" : "opacity-0",
              )}
            />
            <Icon className={clsx("size-4 shrink-0", active ? "text-shell-accent" : "opacity-80")} strokeWidth={1.75} />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}

export function Rail() {
  return (
    <aside className="sticky top-0 hidden h-dvh w-(--rail-w) shrink-0 flex-col border-r border-shell-line bg-shell px-3 pb-4 lg:flex">
      <Link href="/" className="flex h-(--topbar-h) items-center gap-2.5 px-2 no-underline">
        <BrandMark className="size-7" />
        <span className="text-md font-semibold tracking-tight text-shell-ink-strong">FinPulse</span>
      </Link>
      <div className="mt-3">
        <RailNav />
      </div>
      <div className="mt-auto flex flex-col gap-3 border-t border-shell-line px-2 pt-4">
        <ThemeToggle />
        <p className="text-2xs leading-4 text-shell-ink/80">
          Read the market before it moves.
          <br />
          23CSE471 NLP · Team 6
        </p>
      </div>
    </aside>
  );
}
