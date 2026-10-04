"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";

import { useWM } from "./wm";

const KEYS: [string, string][] = [
  ["1 … 7", "Switch workspace"],
  ["h  k", "Focus previous window"],
  ["l  j", "Focus next window"],
  ["f", "Maximise or restore the focused window"],
  ["t", "Cycle layout: master-stack, grid, monocle"],
  ["Esc", "Leave monocle"],
  ["/  or  Ctrl K", "Open the launcher"],
  ["d", "Day or night theme"],
  ["?", "This list"],
  ["← →", "Inside a chart: step through days"],
];

export function KeyHelp() {
  const { helpOpen, setHelpOpen } = useWM();
  return (
    <Dialog.Root open={helpOpen} onOpenChange={setHelpOpen}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/45" />
        <Dialog.Content className="fixed top-1/2 left-1/2 z-50 w-[min(460px,calc(100vw-24px))] -translate-x-1/2 -translate-y-1/2 border border-ring bg-surface shadow-pop">
          <header className="flex h-8 items-center gap-2 border-b border-ring/40 bg-ring-soft px-3 font-mono text-2xs">
            <span className="font-semibold text-accent-ink">help</span>
            <span className="text-ink-3">·</span>
            <Dialog.Title className="font-medium text-ink-2">keybindings</Dialog.Title>
            <Dialog.Close aria-label="Close" className="ml-auto flex size-6 items-center justify-center text-ink-3 hover:text-ink">
              <X className="size-3.5" />
            </Dialog.Close>
          </header>
          <Dialog.Description className="px-3 pt-3 text-sm text-ink-2">
            Keys work anywhere outside a text field, so browser shortcuts stay untouched.
          </Dialog.Description>
          <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 p-3 text-sm">
            {KEYS.map(([k, v]) => (
              <div key={k} className="contents">
                <dt>
                  <kbd className="inline-block min-w-12 border border-line bg-surface-2 px-1.5 py-0.5 text-center text-xs text-ink">{k}</kbd>
                </dt>
                <dd className="text-ink-2">{v}</dd>
              </div>
            ))}
          </dl>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
