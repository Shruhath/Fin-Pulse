"use client";

import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";

/**
 * Both icons render on the server; CSS shows the one matching the theme, so the
 * toggle never needs a mounted-state gate and never flashes the wrong icon.
 */
export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  return (
    <button
      type="button"
      onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
      className="flex h-8 w-fit items-center gap-2 rounded-m px-2 text-xs text-shell-ink transition-colors hover:bg-shell-2 hover:text-shell-ink-strong"
    >
      <Sun className="size-3.5 dark:hidden" strokeWidth={1.75} aria-hidden="true" />
      <Moon className="hidden size-3.5 dark:block" strokeWidth={1.75} aria-hidden="true" />
      <span className="dark:hidden">Dark theme</span>
      <span className="hidden dark:inline">Light theme</span>
    </button>
  );
}
