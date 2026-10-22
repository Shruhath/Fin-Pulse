"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";

import { FocusProvider, useFocus } from "@/components/linked/focus";
import type { CorpusStatus, SearchIndex } from "@/lib/api/types";
import { AppProvider } from "./app-context";
import { MobileTabs, MobileTop } from "./mobile-nav";
import { Palette } from "./palette";
import { Sidebar } from "./sidebar";
import { Toaster } from "./toaster";

/** Leaving a page drops whatever was highlighted on it. */
function ResetFocusOnNavigate() {
  const pathname = usePathname();
  const { clear } = useFocus();
  useEffect(() => clear(), [pathname]); // eslint-disable-line react-hooks/exhaustive-deps
  return null;
}

/** The app frame: sidebar on wide screens, a top bar and a tab bar on narrow ones. */
export function AppShell({
  corpus,
  index,
  preview,
  children,
}: {
  corpus: CorpusStatus | null;
  index: SearchIndex | null;
  preview: boolean;
  children: React.ReactNode;
}) {
  return (
    <AppProvider>
      <FocusProvider>
        <ResetFocusOnNavigate />
        <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-[60] focus:rounded-xl focus:bg-surface focus:px-4 focus:py-2 focus:shadow-pop">
          Skip to content
        </a>
        <Sidebar corpus={corpus} preview={preview} />
        <MobileTop />
        <div className="lg:pl-(--rail-w)">
          {preview && (
            <p className="bg-warn px-4 py-2 text-center text-sm font-medium text-ink-inverse">
              Synthetic preview: every company, filing and figure on screen is invented. Start the stack with <code className="font-mono">make live</code> for real data.
            </p>
          )}
          <main id="main" className="mx-auto w-full max-w-[1180px] px-4 pt-6 pb-28 sm:px-8 lg:pt-10 lg:pb-20">
            {children}
          </main>
        </div>
        <MobileTabs />
        <Palette index={index} />
        <Toaster />
      </FocusProvider>
    </AppProvider>
  );
}
