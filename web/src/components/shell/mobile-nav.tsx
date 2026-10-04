"use client";

import { useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { Menu, X } from "lucide-react";

import { BrandMark } from "./brand";
import { RailNav } from "./rail";
import { ThemeToggle } from "./theme-toggle";

export function MobileNav() {
  const [open, setOpen] = useState(false);
  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger asChild>
        <button
          type="button"
          aria-label="Open navigation"
          className="flex size-8 items-center justify-center rounded-m text-ink-2 hover:bg-surface-2 lg:hidden"
        >
          <Menu className="size-5" strokeWidth={1.75} />
        </button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-shell/50 lg:hidden" />
        <Dialog.Content
          aria-describedby={undefined}
          className="fixed inset-y-0 left-0 z-50 flex w-72 max-w-[85vw] flex-col bg-shell px-3 pb-4 shadow-pop lg:hidden"
        >
          <div className="flex h-(--topbar-h) items-center gap-2.5 px-2">
            <BrandMark className="size-7" />
            <Dialog.Title className="text-md font-semibold text-shell-ink-strong">FinPulse</Dialog.Title>
            <Dialog.Close
              aria-label="Close navigation"
              className="ml-auto flex size-8 items-center justify-center rounded-m text-shell-ink hover:bg-shell-2"
            >
              <X className="size-4" />
            </Dialog.Close>
          </div>
          <div className="mt-3">
            <RailNav onNavigate={() => setOpen(false)} />
          </div>
          <div className="mt-auto border-t border-shell-line px-2 pt-4">
            <ThemeToggle />
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
