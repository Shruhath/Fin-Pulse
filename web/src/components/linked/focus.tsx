"use client";

import { createContext, useContext, useMemo, useState } from "react";

/**
 * Linked focus: the one thing every window in a workspace agrees on. Hovering
 * a chart point, an event marker, a table row, a filing or a claim sets it,
 * and every window highlights the same company, day or source sentence.
 */
export interface Focus {
  entityId: string | null;
  day: string | null;
  /** a character range in a document, e.g. the evidence for a claim */
  span: { documentId: string; start: number; end: number } | null;
}

interface FocusCtx extends Focus {
  setFocus: (f: Partial<Focus>) => void;
  clear: () => void;
}

const Ctx = createContext<FocusCtx | null>(null);
const EMPTY: Focus = { entityId: null, day: null, span: null };

export function FocusProvider({ children }: { children: React.ReactNode }) {
  const [focus, set] = useState<Focus>(EMPTY);
  const value = useMemo<FocusCtx>(
    () => ({ ...focus, setFocus: (f) => set((prev) => ({ ...prev, ...f })), clear: () => set(EMPTY) }),
    [focus],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useFocus() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useFocus must be used inside FocusProvider");
  return ctx;
}
