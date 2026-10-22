"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import * as Dialog from "@radix-ui/react-dialog";
import { Ellipsis, Search, X } from "lucide-react";
import clsx from "clsx";

import { INSIGHTS, isActive, PRIMARY } from "@/lib/nav";
import { useApp } from "./app-context";
import { LogoMark, Wordmark } from "./logo";
import { ThemeToggle } from "./theme-toggle";

/** Phones and narrow windows: a slim top bar and a tab bar at the thumb. */
export function MobileTop() {
  const { setPaletteOpen } = useApp();
  return (
    <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-white/10 bg-rail px-4 text-white lg:hidden">
      <Link href="/" className="flex items-center gap-2 text-white no-underline" aria-label="FinPulse, back to the start page">
        <LogoMark className="size-6" />
        <Wordmark className="text-[1.15rem]" />
      </Link>
      <button type="button" onClick={() => setPaletteOpen(true)} aria-label="Search" className="inline-flex size-10 items-center justify-center rounded-full text-rail-ink hover:bg-white/10">
        <Search className="size-5" aria-hidden="true" />
      </button>
    </header>
  );
}

export function MobileTabs() {
  const pathname = usePathname();
  const [more, setMore] = useState(false);
  const insightActive = INSIGHTS.some((i) => isActive(pathname, i.href));
  const tab = "flex flex-1 flex-col items-center justify-center gap-0.5 text-[0.6875rem] font-medium no-underline transition-colors";

  return (
    <Dialog.Root open={more} onOpenChange={setMore}>
      <nav
        aria-label="Main"
        className="fixed inset-x-0 bottom-0 z-30 flex h-16 border-t border-line bg-surface/95 pb-[env(safe-area-inset-bottom)] backdrop-blur lg:hidden"
      >
        {PRIMARY.map((n) => {
          const on = isActive(pathname, n.href);
          const Icon = n.icon;
          return (
            <Link key={n.key} href={n.href} aria-current={on ? "page" : undefined} className={clsx(tab, on ? "text-brand-ink" : "text-ink-3")}>
              <span className={clsx("flex h-7 w-12 items-center justify-center rounded-full transition-colors", on && "bg-brand-weak")}>
                <Icon className="size-5" strokeWidth={on ? 2.3 : 1.9} aria-hidden="true" />
              </span>
              {n.label}
            </Link>
          );
        })}
        <Dialog.Trigger className={clsx(tab, insightActive ? "text-brand-ink" : "text-ink-3")}>
          <span className={clsx("flex h-7 w-12 items-center justify-center rounded-full", insightActive && "bg-brand-weak")}>
            <Ellipsis className="size-5" aria-hidden="true" />
          </span>
          More
        </Dialog.Trigger>
      </nav>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/40 data-[state=open]:animate-[fade-up_160ms_ease-out]" />
        <Dialog.Content
          aria-describedby={undefined}
          className="fixed inset-x-0 bottom-0 z-50 rounded-t-3xl border border-line bg-surface p-5 pb-[calc(1.25rem+env(safe-area-inset-bottom))] shadow-pop data-[state=open]:animate-[fade-up_240ms_var(--ease-out)]"
        >
          <div className="mb-3 flex items-center justify-between">
            <Dialog.Title className="text-lg font-semibold">Insights</Dialog.Title>
            <Dialog.Close aria-label="Close" className="inline-flex size-9 items-center justify-center rounded-full text-ink-3 hover:bg-surface-2">
              <X className="size-5" aria-hidden="true" />
            </Dialog.Close>
          </div>
          <ul className="space-y-1">
            {INSIGHTS.map((n) => {
              const Icon = n.icon;
              const on = isActive(pathname, n.href);
              return (
                <li key={n.key}>
                  <Link
                    href={n.href}
                    onClick={() => setMore(false)}
                    className={clsx("flex items-center gap-3 rounded-2xl px-3 py-3 no-underline", on ? "bg-brand-weak text-brand-ink" : "hover:bg-surface-2")}
                  >
                    <Icon className="size-5 shrink-0" aria-hidden="true" />
                    <span>
                      <span className="block font-medium">{n.label}</span>
                      <span className="block text-sm text-ink-3">{n.hint}</span>
                    </span>
                  </Link>
                </li>
              );
            })}
          </ul>
          <div className="mt-3 flex items-center justify-between border-t border-line pt-3">
            <ThemeToggle className="text-ink-2 hover:bg-surface-2" />
            <Link href="/" onClick={() => setMore(false)} className="text-sm font-medium text-brand-ink no-underline">
              About FinPulse
            </Link>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
