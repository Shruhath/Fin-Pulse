"use client";

import { createContext, useContext, useMemo, useState } from "react";

/**
 * Linked focus: the one thing every Overview panel agrees on. Hovering a chart
 * point, an event marker, a table row or a filing sets it, and every panel
 * highlights the same company and the same day.
 */
export interface Focus {
  entityId: string | null;
  day: string | null;
}

interface FocusCtx extends Focus {
  setFocus: (f: Partial<Focus>) => void;
  clear: () => void;
}

const Ctx = createContext<FocusCtx | null>(null);

export function FocusProvider({ children }: { children: React.ReactNode }) {
  const [focus, set] = useState<Focus>({ entityId: null, day: null });
  const value = useMemo<FocusCtx>(
    () => ({
      ...focus,
      setFocus: (f) => set((prev) => ({ ...prev, ...f })),
      clear: () => set({ entityId: null, day: null }),
    }),
    [focus],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useFocus() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useFocus must be used inside FocusProvider");
  return ctx;
}
