"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import * as Dialog from "@radix-ui/react-dialog";
import { Command } from "cmdk";
import { Building2, CornerDownLeft, FileText, MessageSquareText, Moon, ScanSearch, Search } from "lucide-react";

import type { SearchIndex } from "@/lib/api/types";
import { ALL_NAV } from "@/lib/nav";
import { useApp } from "./app-context";

const item =
  "flex cursor-pointer items-center gap-3 rounded-xl px-3 py-2.5 text-[0.9375rem] text-ink-2 data-[selected=true]:bg-brand-weak data-[selected=true]:text-ink";
const group =
  "[&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:pt-3 [&_[cmdk-group-heading]]:pb-1 [&_[cmdk-group-heading]]:text-xs [&_[cmdk-group-heading]]:font-semibold [&_[cmdk-group-heading]]:text-ink-3";

/** Search for a page, company or filing, or type a sentence and ask it. */
export function Palette({ index }: { index: SearchIndex | null }) {
  const { paletteOpen, setPaletteOpen } = useApp();
  const router = useRouter();
  const { resolvedTheme, setTheme } = useTheme();
  const [query, setQuery] = useState("");

  const go = (href: string) => {
    setPaletteOpen(false);
    setQuery("");
    router.push(href);
  };
  const looksLikeQuestion = query.trim().split(/\s+/).length >= 3;

  return (
    <Dialog.Root
      open={paletteOpen}
      onOpenChange={(o) => {
        setPaletteOpen(o);
        if (!o) setQuery("");
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-[#0a0d26]/45 backdrop-blur-[2px] data-[state=open]:animate-[fade-up_160ms_ease-out]" />
        <Dialog.Content
          aria-describedby={undefined}
          className="fixed top-[12vh] left-1/2 z-50 w-[min(640px,calc(100vw-24px))] -translate-x-1/2 overflow-hidden rounded-2xl border border-line bg-surface shadow-pop data-[state=open]:animate-[fade-up_220ms_var(--ease-out)]"
        >
          <Dialog.Title className="sr-only">Search FinPulse</Dialog.Title>
          <Command label="Search FinPulse" loop>
            <div className="flex items-center gap-3 border-b border-line px-4">
              <Search className="size-[18px] shrink-0 text-ink-3" aria-hidden="true" />
              <Command.Input
                autoFocus
                value={query}
                onValueChange={setQuery}
                placeholder="Search companies and filings, or ask a question"
                className="h-14 flex-1 bg-transparent text-md text-ink outline-none"
              />
              <kbd className="rounded-md bg-surface-2 px-1.5 py-0.5 text-xs text-ink-3">Esc</kbd>
            </div>
            <Command.List className="max-h-[56vh] overflow-y-auto p-2">
              <Command.Empty className="px-3 py-10 text-center text-sm text-ink-3">Nothing matches. Press Enter to ask it as a question.</Command.Empty>
              {looksLikeQuestion && (
                <Command.Group heading="Ask" className={group}>
                  <Command.Item forceMount value={`ask ${query}`} onSelect={() => go(`/ask?q=${encodeURIComponent(query.trim())}`)} className={item}>
                    <MessageSquareText className="size-[18px] shrink-0 text-brand-ink" aria-hidden="true" />
                    <span className="min-w-0 flex-1 truncate">Ask the filings: “{query.trim()}”</span>
                    <CornerDownLeft className="size-4 text-ink-3" aria-hidden="true" />
                  </Command.Item>
                </Command.Group>
              )}
              <Command.Group heading="Pages" className={group}>
                {ALL_NAV.map((n) => (
                  <Command.Item key={n.key} value={`page ${n.label} ${n.hint}`} onSelect={() => go(n.href)} className={item}>
                    <n.icon className="size-[18px] shrink-0 text-ink-3" aria-hidden="true" />
                    <span className="font-medium text-ink">{n.label}</span>
                    <span className="truncate text-sm text-ink-3">{n.hint}</span>
                  </Command.Item>
                ))}
              </Command.Group>
              {index && index.companies.length > 0 && (
                <Command.Group heading="Companies" className={group}>
                  {index.companies.map((c) => (
                    <Command.Item key={c.id} value={`company ${c.name} ${c.ticker}`} onSelect={() => go(`/companies/${c.id}`)} className={item}>
                      <Building2 className="size-[18px] shrink-0 text-ink-3" aria-hidden="true" />
                      <span className="font-medium text-ink">{c.name}</span>
                      <span className="num text-sm text-ink-3">{c.ticker}</span>
                    </Command.Item>
                  ))}
                </Command.Group>
              )}
              {index && index.filings.length > 0 && (
                <Command.Group heading="Filings" className={group}>
                  {index.filings.map((f) => (
                    <Command.Item key={f.id} value={`filing ${f.source} ${f.title}`} onSelect={() => go(`/filings/${f.id}`)} className={item}>
                      <FileText className="size-[18px] shrink-0 text-ink-3" aria-hidden="true" />
                      <span className="w-11 shrink-0 text-xs font-semibold text-ink-3">{f.source}</span>
                      <span className="truncate">{f.title}</span>
                    </Command.Item>
                  ))}
                </Command.Group>
              )}
              <Command.Group heading="Actions" className={group}>
                <Command.Item value="action analyze a new document" onSelect={() => go("/analyze")} className={item}>
                  <ScanSearch className="size-[18px] shrink-0 text-ink-3" aria-hidden="true" /> Analyze a new document
                </Command.Item>
                <Command.Item
                  value="action switch theme dark light"
                  onSelect={() => {
                    setTheme(resolvedTheme === "dark" ? "light" : "dark");
                    setPaletteOpen(false);
                  }}
                  className={item}
                >
                  <Moon className="size-[18px] shrink-0 text-ink-3" aria-hidden="true" /> Switch between light and dark
                </Command.Item>
              </Command.Group>
            </Command.List>
          </Command>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
