"use client";

import { useSyncExternalStore } from "react";
import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import clsx from "clsx";

const noop = () => () => {};

/** Day and night. Renders after mount so the icon matches the theme that was actually applied. */
export function ThemeToggle({ className, label = true }: { className?: string; label?: boolean }) {
  const { resolvedTheme, setTheme } = useTheme();
  const mounted = useSyncExternalStore(noop, () => true, () => false);
  const dark = mounted && resolvedTheme === "dark";
  return (
    <button
      type="button"
      onClick={() => setTheme(dark ? "light" : "dark")}
      aria-label={dark ? "Switch to the light theme" : "Switch to the dark theme"}
      className={clsx("inline-flex h-9 items-center gap-2 rounded-xl px-2.5 text-sm font-medium transition-colors", className)}
    >
      {dark ? <Sun className="size-[18px]" aria-hidden="true" /> : <Moon className="size-[18px]" aria-hidden="true" />}
      {label && <span>{dark ? "Light theme" : "Dark theme"}</span>}
    </button>
  );
}
