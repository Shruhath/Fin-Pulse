"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useTheme } from "next-themes";
import { Columns2, Grid2x2, Keyboard, Moon, Search, Square, Sun } from "lucide-react";
import clsx from "clsx";

import type { CorpusStatus } from "@/lib/api/types";
import { fmtInt } from "@/lib/format";
import { useWM, type LayoutMode } from "./wm";
import { WORKSPACES } from "./workspaces";

const LAYOUT_META: Record<LayoutMode, { icon: typeof Square; label: string }> = {
  tile: { icon: Columns2, label: "Master and stack" },
  grid: { icon: Grid2x2, label: "Grid" },
  monocle: { icon: Square, label: "Monocle, one window" },
};

export function StatusBar({ corpus, preview }: { corpus: CorpusStatus | null; preview: boolean }) {
  const wm = useWM();
  const focusedTile = wm.tiles.find((t) => t.id === wm.focused);

  return (
    <header className="sticky top-0 z-40 flex h-(--bar-h) shrink-0 items-stretch gap-2 bg-bar px-1.5 font-mono text-2xs text-bar-ink select-none">
      <nav aria-label="Workspaces" className="flex min-w-0 items-stretch overflow-x-auto">
        <span className="hidden items-center px-2 font-semibold tracking-tight text-[#ece7dc] sm:flex">finpulse</span>
        {WORKSPACES.map((w) => {
          const active = wm.workspace.n === w.n;
          return (
            <Link
              key={w.n}
              href={w.href}
              aria-current={active ? "page" : undefined}
              title={`${w.hint} (${w.n})`}
              className={clsx(
                "flex items-center gap-1.5 px-2.5 no-underline transition-colors",
                active ? "bg-accent font-semibold text-[#0e1015]" : "hover:bg-white/8 hover:text-[#ece7dc]",
              )}
            >
              <span className={clsx(active ? "" : "text-[#ece7dc]")}>{w.n}</span>
              <span className={clsx(active ? "inline" : "hidden md:inline")}>{w.label}</span>
            </Link>
          );
        })}
      </nav>

      <p className="hidden min-w-0 flex-1 items-center justify-center truncate text-center xl:flex" aria-live="polite">
        {focusedTile ? (
          <>
            <span className="text-accent">{focusedTile.cls}</span>
            <span className="px-1.5 opacity-60">·</span>
            <span className="truncate text-[#ece7dc]">{focusedTile.title}</span>
          </>
        ) : (
          <span className="opacity-70">press ? for keys · / to launch</span>
        )}
      </p>

      <div className="ml-auto flex items-stretch">
        <button
          type="button"
          onClick={() => wm.setLauncherOpen(true)}
          className="flex items-center gap-1.5 px-2.5 hover:bg-white/8 hover:text-[#ece7dc]"
          aria-label="Open launcher"
        >
          <Search className="size-3.5" />
          <span className="hidden lg:inline">launch</span>
          <kbd className="hidden text-[10px] opacity-60 lg:inline">ctrl k</kbd>
        </button>
        <Segment label="Layout" className="hidden lg:flex">
          {(Object.keys(LAYOUT_META) as LayoutMode[]).map((l) => {
            const { icon: Icon, label } = LAYOUT_META[l];
            const on = wm.layout === l;
            return (
              <button
                key={l}
                type="button"
                aria-pressed={on}
                aria-label={label}
                title={`${label} (t cycles)`}
                onClick={() => wm.setLayout(l)}
                className={clsx("flex w-7 items-center justify-center", on ? "text-accent" : "hover:text-[#ece7dc]")}
              >
                <Icon className="size-3.5" strokeWidth={2} />
              </button>
            );
          })}
        </Segment>
        <Suspense fallback={null}>
          <WindowSwitch />
        </Suspense>
        <Item className="hidden lg:flex">
          {corpus ? (
            <>
              <span className="text-[#ece7dc]">{fmtInt(corpus.documents)}</span> docs
            </>
          ) : (
            <span className="text-accent">api offline</span>
          )}
          {preview && <span className="text-accent">· preview</span>}
        </Item>
        <Clock />
        <ThemeButton />
        <button
          type="button"
          onClick={() => wm.setHelpOpen(true)}
          aria-label="Keyboard shortcuts"
          title="Keyboard shortcuts (?)"
          className="hidden items-center px-2 hover:bg-white/8 hover:text-[#ece7dc] sm:flex"
        >
          <Keyboard className="size-3.5" />
        </button>
      </div>
    </header>
  );
}

function Item({ children, className }: { children: React.ReactNode; className?: string }) {
  return <span className={clsx("items-center gap-1.5 border-l border-white/8 px-2.5", className ?? "flex")}>{children}</span>;
}

function Segment({ label, children, className }: { label: string; children: React.ReactNode; className?: string }) {
  return (
    <div role="group" aria-label={label} className={clsx("items-stretch border-l border-white/8 px-1", className ?? "flex")}>
      {children}
    </div>
  );
}

function WindowSwitch() {
  const pathname = usePathname();
  const params = useSearchParams();
  const current = params.get("w") ?? "30d";
  return (
    <Segment label="Time window">
      {(["7d", "30d", "90d"] as const).map((w) => {
        const next = new URLSearchParams(params);
        if (w === "30d") next.delete("w");
        else next.set("w", w);
        const qs = next.toString();
        const on = current === w;
        return (
          <Link
            key={w}
            href={qs ? `${pathname}?${qs}` : pathname}
            scroll={false}
            aria-pressed={on}
            aria-label={`Last ${w.replace("d", " days")}`}
            className={clsx("flex items-center px-1.5 no-underline", on ? "text-accent" : "hover:text-[#ece7dc]")}
          >
            {w}
          </Link>
        );
      })}
    </Segment>
  );
}

/** IST clock and NSE regular-session state (Mon–Fri 09:15–15:30; exchange holidays not modelled). */
function Clock() {
  const [now, setNow] = useState<Date | null>(null);
  useEffect(() => {
    setNow(new Date());
    const id = window.setInterval(() => setNow(new Date()), 15_000);
    return () => window.clearInterval(id);
  }, []);
  if (!now) return <Item className="hidden w-[148px] sm:flex">{null}</Item>;
  const ist = new Date(now.getTime() + (5.5 * 60 + now.getTimezoneOffset()) * 60_000);
  const mins = ist.getHours() * 60 + ist.getMinutes();
  const weekday = ist.getDay() >= 1 && ist.getDay() <= 5;
  const open = weekday && mins >= 555 && mins < 930;
  const hhmm = `${String(ist.getHours()).padStart(2, "0")}:${String(ist.getMinutes()).padStart(2, "0")}`;
  return (
    <Item className="hidden sm:flex">
      <span
        title="NSE regular session, 09:15 to 15:30 IST on weekdays. Exchange holidays are not modelled."
        className={clsx("flex items-center gap-1", open ? "text-pos" : "")}
      >
        <span className={clsx("size-1.5", open ? "bg-pos" : "border border-current")} aria-hidden="true" />
        nse {open ? "open" : "closed"}
      </span>
      <time className="text-[#ece7dc]" dateTime={now.toISOString()}>
        {hhmm} ist
      </time>
    </Item>
  );
}

function ThemeButton() {
  const { resolvedTheme, setTheme } = useTheme();
  return (
    <button
      type="button"
      onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
      aria-label="Toggle day and night theme"
      title="Day / night (d)"
      className="flex items-center border-l border-white/8 px-2 hover:bg-white/8 hover:text-[#ece7dc]"
    >
      <Sun className="hidden size-3.5 dark:block" />
      <Moon className="size-3.5 dark:hidden" />
    </button>
  );
}
