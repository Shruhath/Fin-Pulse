"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { FlaskConical, Search } from "lucide-react";
import clsx from "clsx";

import type { CorpusStatus } from "@/lib/api/types";
import { fmtInt } from "@/lib/format";
import { INSIGHTS, isActive, PRIMARY, type NavItem } from "@/lib/nav";
import { useApp } from "./app-context";
import { LogoMark, Wordmark } from "./logo";
import { ThemeToggle } from "./theme-toggle";
import { useSlider } from "./use-slider";

function NavLink({ item, active }: { item: NavItem; active: boolean }) {
  const Icon = item.icon;
  return (
    <li>
      <Link
        href={item.href}
        data-active={active}
        aria-current={active ? "page" : undefined}
        className={clsx(
          "relative z-[1] flex h-10 items-center gap-3 rounded-xl px-3 text-[0.9375rem] font-medium no-underline transition-colors duration-200",
          active ? "text-white" : "text-rail-ink hover:bg-white/8 hover:text-white",
        )}
      >
        <Icon className="size-[18px] shrink-0" strokeWidth={active ? 2.25 : 1.9} aria-hidden="true" />
        {item.label}
      </Link>
    </li>
  );
}

export function Sidebar({ corpus, preview }: { corpus: CorpusStatus | null; preview: boolean }) {
  const pathname = usePathname();
  const { setPaletteOpen } = useApp();
  const [navRef, box] = useSlider<HTMLElement>([pathname]);

  return (
    <aside
      className="fixed inset-y-0 left-0 z-30 hidden w-(--rail-w) flex-col bg-rail text-rail-ink lg:flex"
    >
      <Link href="/" className="flex h-16 shrink-0 items-center gap-2.5 px-5 text-white no-underline" aria-label="FinPulse, back to the start page">
        <LogoMark />
        <Wordmark />
      </Link>

      <div className="px-3">
        <button
          type="button"
          onClick={() => setPaletteOpen(true)}
          className="flex h-10 w-full items-center gap-2.5 rounded-xl bg-white/10 px-3 text-sm text-rail-ink transition-colors hover:bg-white/16 hover:text-white"
        >
          <Search className="size-4" aria-hidden="true" />
          <span className="flex-1 text-left">Search</span>
          <kbd className="rounded-md bg-white/12 px-1.5 py-0.5 text-xs font-medium text-rail-ink">Ctrl K</kbd>
        </button>
      </div>

      <nav ref={navRef} aria-label="Main" className="relative mt-4 min-h-0 flex-1 overflow-y-auto px-3 pb-4">
        {box && (
          <span
            aria-hidden="true"
            className="absolute right-3 left-3 top-0 rounded-xl bg-white/14 transition-[transform,height] duration-300 ease-(--ease-out)"
            style={{ height: box.h, transform: `translateY(${box.y}px)` }}
          >
            <span className="absolute top-1/2 -left-3 h-5 w-1.5 -translate-y-1/2 rounded-r-full bg-white" />
          </span>
        )}
        <ul className="space-y-0.5">
          {PRIMARY.map((n) => (
            <NavLink key={n.key} item={n} active={isActive(pathname, n.href)} />
          ))}
        </ul>
        <p className="mt-6 mb-1.5 px-3 text-xs font-semibold text-rail-ink/70">Insights</p>
        <ul className="space-y-0.5">
          {INSIGHTS.map((n) => (
            <NavLink key={n.key} item={n} active={isActive(pathname, n.href)} />
          ))}
        </ul>
      </nav>

      <div className="space-y-1 border-t border-white/12 px-3 py-3">
        {preview && (
          <p className="mb-2 flex items-center gap-2 rounded-xl bg-warn px-3 py-2 text-xs font-semibold text-ink-inverse">
            <FlaskConical className="size-3.5 shrink-0" aria-hidden="true" />
            Synthetic preview data
          </p>
        )}
        <ThemeToggle className="w-full text-rail-ink hover:bg-white/8 hover:text-white" />
        <p className="px-2.5 pt-1 text-xs leading-5 text-rail-ink/75">
          {corpus ? (
            <>
              <span className="num font-medium text-rail-ink">{fmtInt(corpus.documents)}</span> filings,{" "}
              <span className="num font-medium text-rail-ink">{fmtInt(corpus.entities)}</span> companies
            </>
          ) : (
            "API offline"
          )}
          <br />
          Research software, not investment advice.
        </p>
      </div>
    </aside>
  );
}
