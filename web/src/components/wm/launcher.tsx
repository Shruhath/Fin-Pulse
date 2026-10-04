"use client";

import { useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import * as Dialog from "@radix-ui/react-dialog";
import { Command } from "cmdk";
import { Building2, Columns2, FileText, Maximize2, Moon, ScanSearch } from "lucide-react";

import type { SearchIndex } from "@/lib/api/types";
import { useWM } from "./wm";
import { WORKSPACES } from "./workspaces";

const itemCls =
  "group flex cursor-pointer items-center gap-3 px-3 py-1.5 text-sm text-ink-2 data-[selected=true]:bg-accent data-[selected=true]:text-ink-inverse";
const groupCls =
  "[&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:pt-3 [&_[cmdk-group-heading]]:pb-1 [&_[cmdk-group-heading]]:font-mono [&_[cmdk-group-heading]]:text-2xs [&_[cmdk-group-heading]]:text-ink-3";

/** Keyboard-first launcher: workspaces, companies, filings and window actions. */
export function Launcher({ index }: { index: SearchIndex | null }) {
  const wm = useWM();
  const router = useRouter();
  const { resolvedTheme, setTheme } = useTheme();
  const run = (fn: () => void) => {
    wm.setLauncherOpen(false);
    fn();
  };

  return (
    <Dialog.Root open={wm.launcherOpen} onOpenChange={wm.setLauncherOpen}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/45" />
        <Dialog.Content
          aria-describedby={undefined}
          className="fixed top-[16vh] left-1/2 z-50 w-[min(640px,calc(100vw-24px))] -translate-x-1/2 border border-ring bg-surface shadow-pop"
        >
          <Dialog.Title className="sr-only">Launcher</Dialog.Title>
          <Command label="Launcher" loop>
            <div className="flex items-center gap-2 border-b border-line px-3">
              <span className="font-mono text-sm font-semibold text-accent" aria-hidden="true">
                run ›
              </span>
              <Command.Input
                autoFocus
                placeholder="workspace, company, filing or action"
                className="h-11 flex-1 bg-transparent font-mono text-sm text-ink outline-none"
              />
            </div>
            <Command.List className="max-h-[56vh] overflow-y-auto pb-2">
              <Command.Empty className="px-3 py-8 text-center font-mono text-xs text-ink-3">no match</Command.Empty>
              <Command.Group heading="workspaces" className={groupCls}>
                {WORKSPACES.map((w) => (
                  <Command.Item key={w.n} value={`workspace ${w.n} ${w.label} ${w.hint}`} onSelect={() => run(() => router.push(w.href))} className={itemCls}>
                    <span className="w-4 font-mono text-xs opacity-70">{w.n}</span>
                    <w.icon className="size-4 shrink-0 opacity-80" strokeWidth={1.75} />
                    <span className="font-medium">{w.label}</span>
                    <span className="truncate text-xs opacity-70">{w.hint}</span>
                  </Command.Item>
                ))}
              </Command.Group>
              {index && index.companies.length > 0 && (
                <Command.Group heading="companies" className={groupCls}>
                  {index.companies.map((c) => (
                    <Command.Item key={c.id} value={`company ${c.name} ${c.ticker}`} onSelect={() => run(() => router.push(`/companies/${c.id}`))} className={itemCls}>
                      <Building2 className="size-4 shrink-0 opacity-70" strokeWidth={1.75} />
                      <span className="font-medium">{c.name}</span>
                      <span className="font-mono text-2xs opacity-70">{c.ticker}</span>
                    </Command.Item>
                  ))}
                </Command.Group>
              )}
              {index && index.filings.length > 0 && (
                <Command.Group heading="filings" className={groupCls}>
                  {index.filings.map((f) => (
                    <Command.Item key={f.id} value={`filing ${f.source} ${f.title}`} onSelect={() => run(() => router.push(`/filings/${f.id}`))} className={itemCls}>
                      <FileText className="size-4 shrink-0 opacity-70" strokeWidth={1.75} />
                      <span className="w-10 font-mono text-2xs opacity-70">{f.source}</span>
                      <span className="truncate">{f.title}</span>
                    </Command.Item>
                  ))}
                </Command.Group>
              )}
              <Command.Group heading="actions" className={groupCls}>
                <Command.Item value="action analyze run pipeline new document" onSelect={() => run(() => router.push("/analyze"))} className={itemCls}>
                  <ScanSearch className="size-4 opacity-70" strokeWidth={1.75} /> Analyze a new document
                </Command.Item>
                <Command.Item value="action cycle layout tile grid monocle" onSelect={() => run(wm.cycleLayout)} className={itemCls}>
                  <Columns2 className="size-4 opacity-70" strokeWidth={1.75} /> Cycle layout
                  <kbd className="ml-auto text-2xs opacity-60">t</kbd>
                </Command.Item>
                <Command.Item value="action maximise focused window monocle" onSelect={() => run(wm.toggleMonocle)} className={itemCls}>
                  <Maximize2 className="size-4 opacity-70" strokeWidth={1.75} /> Maximise focused window
                  <kbd className="ml-auto text-2xs opacity-60">f</kbd>
                </Command.Item>
                <Command.Item
                  value="action theme day night dark light"
                  onSelect={() => run(() => setTheme(resolvedTheme === "dark" ? "light" : "dark"))}
                  className={itemCls}
                >
                  <Moon className="size-4 opacity-70" strokeWidth={1.75} /> Switch day / night theme
                  <kbd className="ml-auto text-2xs opacity-60">d</kbd>
                </Command.Item>
              </Command.Group>
            </Command.List>
          </Command>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
