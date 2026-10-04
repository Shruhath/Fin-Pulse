"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useTheme } from "next-themes";

import { WORKSPACES, workspaceFor } from "./workspaces";

export type LayoutMode = "tile" | "grid" | "monocle";
export const LAYOUTS: LayoutMode[] = ["tile", "grid", "monocle"];

export interface Toast {
  id: number;
  app: string;
  title: string;
  body?: string;
  tone?: "info" | "ok" | "warn" | "error";
}

interface TileInfo {
  id: string;
  cls: string;
  title: string;
}

interface WM {
  workspace: (typeof WORKSPACES)[number];
  /** -1 when the last switch moved left, 1 when it moved right */
  direction: number;
  layout: LayoutMode;
  ratio: number;
  setLayout: (l: LayoutMode) => void;
  cycleLayout: () => void;
  setRatio: (r: number) => void;
  tiles: TileInfo[];
  registerTiles: (tiles: TileInfo[]) => void;
  focused: string | null;
  focusTile: (id: string | null) => void;
  moveFocus: (step: number) => void;
  toggleMonocle: () => void;
  launcherOpen: boolean;
  setLauncherOpen: (o: boolean) => void;
  helpOpen: boolean;
  setHelpOpen: (o: boolean) => void;
  toasts: Toast[];
  notify: (t: Omit<Toast, "id">) => void;
  dismiss: (id: number) => void;
  /** Workspace registers a callback that snapshots tile geometry for GSAP Flip. */
  flipCaptureRef: React.MutableRefObject<(() => void) | null>;
}

const Ctx = createContext<WM | null>(null);

type Persisted = Record<string, { layout: LayoutMode; ratio: number }>;
const KEY = "finpulse.wm.v1";

// Layouts persist per workspace in localStorage, read as an external store so
// the server render and the first client render agree.
const EVT = "finpulse-wm-layout";
function subscribe(cb: () => void) {
  window.addEventListener("storage", cb);
  window.addEventListener(EVT, cb);
  return () => {
    window.removeEventListener("storage", cb);
    window.removeEventListener(EVT, cb);
  };
}
function snapshot() {
  try {
    return localStorage.getItem(KEY) ?? "{}";
  } catch {
    return "{}";
  }
}
function parse(raw: string): Persisted {
  try {
    return JSON.parse(raw) as Persisted;
  } catch {
    return {};
  }
}

export function WMProvider({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { resolvedTheme, setTheme } = useTheme();
  const workspace = workspaceFor(pathname);

  const raw = useSyncExternalStore(subscribe, snapshot, () => "{}");
  const persisted = useMemo(() => parse(raw), [raw]);
  const [tiles, setTiles] = useState<TileInfo[]>([]);
  const [focused, setFocused] = useState<string | null>(null);
  const [launcherOpen, setLauncherOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const flipCaptureRef = useRef<(() => void) | null>(null);
  const [lastN, setLastN] = useState(workspace.n);
  const [direction, setDirection] = useState(0);
  const toastId = useRef(0);

  // Workspace switch: derive slide direction and drop focus during render.
  if (workspace.n !== lastN) {
    setDirection(Math.sign(workspace.n - lastN));
    setLastN(workspace.n);
    setFocused(null);
  }

  const current = persisted[workspace.key] ?? { layout: workspace.layout as LayoutMode, ratio: workspace.ratio };

  const save = useCallback(
    (patch: Partial<{ layout: LayoutMode; ratio: number }>) => {
      const p = parse(snapshot());
      const next = { ...p, [workspace.key]: { ...(p[workspace.key] ?? { layout: workspace.layout, ratio: workspace.ratio }), ...patch } };
      try {
        localStorage.setItem(KEY, JSON.stringify(next));
      } catch {
        /* storage unavailable: the layout still changes for this session below */
      }
      window.dispatchEvent(new Event(EVT));
    },
    [workspace.key, workspace.layout, workspace.ratio],
  );

  const setLayout = useCallback(
    (layout: LayoutMode) => {
      flipCaptureRef.current?.();
      save({ layout });
    },
    [save],
  );

  const cycleLayout = useCallback(() => {
    setLayout(LAYOUTS[(LAYOUTS.indexOf(current.layout) + 1) % LAYOUTS.length]);
  }, [current.layout, setLayout]);

  const toggleMonocle = useCallback(() => {
    setLayout(current.layout === "monocle" ? "tile" : "monocle");
  }, [current.layout, setLayout]);

  const focusTile = useCallback((id: string | null) => setFocused(id), []);

  // a workspace arrives with its master window focused
  const registerTiles = useCallback((ts: TileInfo[]) => {
    setTiles(ts);
    setFocused((f) => f ?? ts[0]?.id ?? null);
  }, []);

  const moveFocus = useCallback(
    (step: number) => {
      if (tiles.length === 0) return;
      const i = focused ? tiles.findIndex((t) => t.id === focused) : -1;
      const next = tiles[(i + step + tiles.length) % tiles.length];
      if (current.layout === "monocle") flipCaptureRef.current?.();
      setFocused(next.id);
      requestAnimationFrame(() => document.querySelector<HTMLElement>(`[data-tile="${next.id}"]`)?.focus({ preventScroll: false }));
    },
    [tiles, focused, current.layout],
  );

  const notify = useCallback((t: Omit<Toast, "id">) => {
    const id = ++toastId.current;
    setToasts((ts) => [...ts.slice(-3), { ...t, id }]);
    window.setTimeout(() => setToasts((ts) => ts.filter((x) => x.id !== id)), 6000);
  }, []);

  const dismiss = useCallback((id: number) => setToasts((ts) => ts.filter((x) => x.id !== id)), []);

  // Keyboard: plain keys when not typing, so browser tab shortcuts stay intact.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      const typing = !!t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName));
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setLauncherOpen((o) => !o);
        return;
      }
      if (e.altKey && e.code === "Space") {
        e.preventDefault();
        setLauncherOpen(true);
        return;
      }
      if (typing || e.ctrlKey || e.metaKey || e.altKey || launcherOpen) return;
      const k = e.key;
      if (/^[1-7]$/.test(k)) {
        e.preventDefault();
        router.push(WORKSPACES[Number(k) - 1].href);
      } else if (k === "l" || k === "j") {
        e.preventDefault();
        moveFocus(1);
      } else if (k === "h" || k === "k") {
        e.preventDefault();
        moveFocus(-1);
      } else if (k === "f") {
        e.preventDefault();
        toggleMonocle();
      } else if (k === "t") {
        e.preventDefault();
        cycleLayout();
      } else if (k === "/") {
        e.preventDefault();
        setLauncherOpen(true);
      } else if (k === "?") {
        e.preventDefault();
        setHelpOpen((o) => !o);
      } else if (k === "Escape" && current.layout === "monocle") {
        setLayout("tile");
      } else if (k === "d") {
        setTheme(resolvedTheme === "dark" ? "light" : "dark");
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [router, moveFocus, toggleMonocle, cycleLayout, setLayout, current.layout, launcherOpen, resolvedTheme, setTheme]);

  const value = useMemo<WM>(
    () => ({
      workspace,
      direction,
      layout: current.layout,
      ratio: current.ratio,
      setLayout,
      cycleLayout,
      setRatio: (ratio) => save({ ratio }),
      tiles,
      registerTiles,
      focused,
      focusTile,
      moveFocus,
      toggleMonocle,
      launcherOpen,
      setLauncherOpen,
      helpOpen,
      setHelpOpen,
      toasts,
      notify,
      dismiss,
      flipCaptureRef,
    }),
    [workspace, direction, current.layout, current.ratio, setLayout, cycleLayout, save, registerTiles, tiles, focused, focusTile, moveFocus, toggleMonocle, launcherOpen, helpOpen, toasts, notify, dismiss],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useWM() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useWM must be used inside WMProvider");
  return ctx;
}
