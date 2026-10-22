"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";

export interface Toast {
  id: number;
  title: string;
  body?: string;
  tone?: "info" | "ok" | "warn" | "error";
}

interface AppCtx {
  paletteOpen: boolean;
  setPaletteOpen: (open: boolean) => void;
  toasts: Toast[];
  notify: (t: Omit<Toast, "id">) => void;
  dismiss: (id: number) => void;
}

const Ctx = createContext<AppCtx | null>(null);

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const next = useRef(0);

  const notify = useCallback((t: Omit<Toast, "id">) => {
    const id = ++next.current;
    setToasts((all) => [...all.slice(-2), { ...t, id }]);
    window.setTimeout(() => setToasts((all) => all.filter((x) => x.id !== id)), 6500);
  }, []);
  const dismiss = useCallback((id: number) => setToasts((all) => all.filter((x) => x.id !== id)), []);

  // Ctrl or Cmd K opens search anywhere; a bare "/" does too when no field has the keyboard.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement | null;
      const typing = !!el && (el.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName));
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((o) => !o);
      } else if (e.key === "/" && !typing && !e.ctrlKey && !e.metaKey && !e.altKey) {
        e.preventDefault();
        setPaletteOpen(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const value = useMemo(() => ({ paletteOpen, setPaletteOpen, toasts, notify, dismiss }), [paletteOpen, toasts, notify, dismiss]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useApp() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useApp must be used inside AppProvider");
  return ctx;
}
