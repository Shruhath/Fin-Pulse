"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import * as Dialog from "@radix-ui/react-dialog";
import { Command } from "cmdk";
import { CornerDownLeft, Search } from "lucide-react";

import { NAV } from "./nav";

/**
 * ⌘K / Ctrl+K palette. Navigation only for now; company and filing search is
 * wired to the API's hybrid search endpoint once the backend serves it.
 */
export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const router = useRouter();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const go = (href: string) => {
    setOpen(false);
    router.push(href);
  };

  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger asChild>
        <button
          type="button"
          className="flex h-8 w-full max-w-md items-center gap-2 rounded-m border border-line bg-surface-2 px-2.5 text-left text-sm text-ink-3 transition-colors hover:border-line-strong hover:text-ink-2"
        >
          <Search className="size-4 shrink-0" strokeWidth={1.75} aria-hidden="true" />
          <span className="flex-1 truncate">Search companies, filings, events</span>
          <kbd className="hidden rounded-s border border-line bg-surface px-1.5 font-sans text-2xs font-medium text-ink-3 sm:inline">
            Ctrl K
          </kbd>
        </button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-shell/40 backdrop-blur-[2px]" />
        <Dialog.Content
          aria-describedby={undefined}
          className="fixed top-[12vh] left-1/2 z-50 w-[min(640px,calc(100vw-32px))] -translate-x-1/2 overflow-hidden rounded-l border border-line bg-surface shadow-pop"
        >
          <Dialog.Title className="sr-only">Search FinPulse</Dialog.Title>
          <Command label="Search FinPulse" className="flex flex-col">
            <div className="flex items-center gap-2 border-b border-line px-3">
              <Search className="size-4 text-ink-3" strokeWidth={1.75} aria-hidden="true" />
              <Command.Input
                autoFocus
                placeholder="Jump to a section…"
                className="h-12 flex-1 bg-transparent text-md text-ink outline-none"
              />
            </div>
            <Command.List className="max-h-[50vh] overflow-y-auto p-1.5">
              <Command.Empty className="px-3 py-6 text-center text-sm text-ink-3">
                Nothing matches. Company and filing search arrives with the API.
              </Command.Empty>
              <Command.Group heading="Go to" className="[&_[cmdk-group-heading]]:px-2.5 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-2xs [&_[cmdk-group-heading]]:font-semibold [&_[cmdk-group-heading]]:text-ink-3">
                {NAV.map(({ href, label, hint, icon: Icon }) => (
                  <Command.Item
                    key={href}
                    value={`${label} ${hint}`}
                    onSelect={() => go(href)}
                    className="group flex cursor-pointer items-center gap-3 rounded-m px-2.5 py-2 text-sm text-ink-2 data-[selected=true]:bg-accent-weak data-[selected=true]:text-ink"
                  >
                    <Icon className="size-4 shrink-0 text-ink-3 group-data-[selected=true]:text-accent" strokeWidth={1.75} aria-hidden="true" />
                    <span className="font-medium text-ink">{label}</span>
                    <span className="truncate text-ink-3">{hint}</span>
                    <CornerDownLeft className="ml-auto size-3.5 opacity-0 group-data-[selected=true]:opacity-60" aria-hidden="true" />
                  </Command.Item>
                ))}
              </Command.Group>
            </Command.List>
          </Command>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
