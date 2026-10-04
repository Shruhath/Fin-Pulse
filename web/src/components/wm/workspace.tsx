"use client";

import { useEffect, useLayoutEffect, useMemo, useRef } from "react";
import { gsap } from "gsap";
import { Flip } from "gsap/Flip";
import { useGSAP } from "@gsap/react";
import { Maximize2, Minimize2 } from "lucide-react";
import clsx from "clsx";

import { FocusProvider } from "@/components/linked/focus";
import { useWM } from "./wm";

gsap.registerPlugin(Flip);

export interface TileSpec {
  id: string;
  /** window class shown in the title bar, e.g. "chart" */
  cls: string;
  title: string;
  meta?: React.ReactNode;
  /** relative height in the stack column */
  weight?: number;
  /** minimum body height when tiles stack on small screens */
  mobileMinH?: number;
  /** body padding off for edge-to-edge content (tables, charts) */
  flush?: boolean;
  node: React.ReactNode;
}

const reduced = () => typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/**
 * One workspace: tiles laid out master-stack, as a grid, or one at a time
 * (monocle). Retiling is animated with GSAP Flip so windows physically slide
 * into their new slots.
 */
export function Workspace({ tiles }: { tiles: TileSpec[] }) {
  const wm = useWM();
  const { layout, ratio, focused, registerTiles, flipCaptureRef, direction } = wm;
  const rootRef = useRef<HTMLDivElement>(null);
  const flipState = useRef<Flip.FlipState | null>(null);
  const ids = tiles.map((t) => t.id).join("|");

  useEffect(() => {
    registerTiles(tiles.map(({ id, cls, title }) => ({ id, cls, title })));
    // ids captures every structural change; titles are static per page
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ids, registerTiles]);

  useEffect(() => {
    flipCaptureRef.current = () => {
      if (!rootRef.current || reduced()) return;
      flipState.current = Flip.getState(rootRef.current.querySelectorAll("[data-tile]"));
    };
    return () => {
      flipCaptureRef.current = null;
    };
  }, [flipCaptureRef]);

  useLayoutEffect(() => {
    if (!flipState.current) return;
    Flip.from(flipState.current, {
      duration: 0.55,
      ease: "expo.inOut",
      absolute: true,
      onEnter: (els) => gsap.fromTo(els, { opacity: 0, scale: 0.97 }, { opacity: 1, scale: 1, duration: 0.35, ease: "power2.out" }),
    });
    flipState.current = null;
  }, [layout, focused]);

  // Workspace switch: tiles slide in from the side we came from, staggered.
  useGSAP(
    () => {
      const mm = gsap.matchMedia();
      mm.add("(prefers-reduced-motion: no-preference)", () => {
        gsap.from("[data-tile]", {
          opacity: 0,
          x: direction * 28,
          y: direction === 0 ? 10 : 0,
          duration: 0.55,
          stagger: 0.05,
          ease: "expo.out",
          clearProps: "transform,opacity",
        });
      });
      return () => mm.revert();
    },
    { scope: rootRef },
  );

  const grid = useMemo(() => {
    const n = tiles.length;
    if (layout === "monocle" || n === 1) return { cols: "minmax(0,1fr)", rows: "minmax(0,1fr)", gutter: false };
    if (layout === "grid") {
      const c = n <= 2 ? n : n <= 4 ? 2 : 3;
      const r = Math.ceil(n / c);
      return { cols: `repeat(${c}, minmax(0,1fr))`, rows: `repeat(${r}, minmax(0,1fr))`, gutter: false };
    }
    const stack = tiles.slice(1);
    return {
      cols: `calc(${(ratio * 100).toFixed(2)}% - 4px) var(--gap) minmax(0,1fr)`,
      rows: stack.map((t) => `minmax(0,${t.weight ?? 1}fr)`).join(" "),
      gutter: true,
    };
  }, [tiles, layout, ratio]);

  const visibleId = layout === "monocle" ? (focused && tiles.some((t) => t.id === focused) ? focused : tiles[0].id) : null;

  return (
    <FocusProvider>
      <div
        ref={rootRef}
        className="flex flex-col gap-(--gap) p-(--gap) lg:grid lg:h-full lg:min-h-0 lg:[grid-template-columns:var(--cols)] lg:[grid-template-rows:var(--rows)] lg:[column-gap:0] lg:[row-gap:var(--gap)]"
        style={{ "--cols": grid.cols, "--rows": grid.rows } as React.CSSProperties}
      >
        {tiles.map((t, i) => {
          let col = "auto";
          let row = "auto";
          if (layout === "tile" && tiles.length > 1) {
            col = i === 0 ? "1" : "3";
            row = i === 0 ? "1 / -1" : String(i);
          }
          if (layout === "grid") col = "auto";
          const hidden = visibleId !== null && t.id !== visibleId;
          return (
            <Tile key={t.id} spec={t} hidden={hidden} col={col} row={row} gridMode={layout === "grid"} />
          );
        })}
        {grid.gutter && <Gutter />}
      </div>
    </FocusProvider>
  );
}

function Tile({ spec, hidden, col, row, gridMode }: { spec: TileSpec; hidden: boolean; col: string; row: string; gridMode: boolean }) {
  const { focused, focusTile, layout, setLayout } = useWM();
  const isFocused = focused === spec.id;
  const headingId = `tile-${spec.id}`;
  const monocle = layout === "monocle";

  return (
    <section
      data-tile={spec.id}
      tabIndex={-1}
      aria-labelledby={headingId}
      hidden={hidden}
      onPointerDownCapture={() => focusTile(spec.id)}
      onFocusCapture={() => focusTile(spec.id)}
      className={clsx(
        "relative flex min-h-0 min-w-0 flex-col border bg-surface outline-none transition-[border-color,box-shadow] duration-200",
        isFocused ? "z-[1] border-ring shadow-[0_0_0_1px_var(--focus-ring-soft),0_14px_40px_-18px_rgba(0,0,0,0.7)]" : "border-line",
        !gridMode && "lg:[grid-column:var(--col)] lg:[grid-row:var(--row)]",
        gridMode && spec.id && "lg:[grid-column:auto] lg:[grid-row:auto]",
      )}
      style={{ "--col": col, "--row": row } as React.CSSProperties}
    >
      <header
        className={clsx(
          "flex h-8 shrink-0 items-center gap-2 border-b px-2.5 font-mono text-2xs",
          isFocused ? "border-ring/40 bg-ring-soft" : "border-line bg-surface-2",
        )}
      >
        <span className={clsx("font-semibold", isFocused ? "text-accent-ink" : "text-ink-3")}>{spec.cls}</span>
        <span className="text-ink-3" aria-hidden="true">
          ·
        </span>
        <h2 id={headingId} className="min-w-0 truncate font-medium text-ink-2">
          {spec.title}
        </h2>
        <div className="ml-auto flex min-w-0 items-center gap-3 text-ink-3">{spec.meta}</div>
        <button
          type="button"
          onClick={() => {
            focusTile(spec.id);
            setLayout(monocle ? "tile" : "monocle");
          }}
          aria-label={monocle ? `Restore ${spec.title} to the tiled layout` : `Maximise ${spec.title}`}
          title={monocle ? "Restore (f)" : "Maximise (f)"}
          className="-mr-1 flex size-6 shrink-0 items-center justify-center text-ink-3 transition-colors hover:bg-surface-3 hover:text-ink"
        >
          {monocle ? <Minimize2 className="size-3.5" /> : <Maximize2 className="size-3.5" />}
        </button>
      </header>
      <div
        className={clsx(
          "@container flex-1 overflow-auto [min-height:var(--mh,0px)] lg:[min-height:0]",
          !spec.flush && "p-3",
        )}
        style={{ "--mh": spec.mobileMinH ? `${spec.mobileMinH}px` : undefined } as React.CSSProperties}
      >
        {spec.node}
      </div>
    </section>
  );
}

function Gutter() {
  const { ratio, setRatio } = useWM();
  const drag = useRef(false);

  const onMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!drag.current) return;
    const parent = e.currentTarget.parentElement!.getBoundingClientRect();
    setRatio(Math.min(0.78, Math.max(0.3, (e.clientX - parent.left) / parent.width)));
  };

  return (
    <div
      role="separator"
      aria-orientation="vertical"
      aria-label="Resize master window"
      aria-valuemin={30}
      aria-valuemax={78}
      aria-valuenow={Math.round(ratio * 100)}
      tabIndex={0}
      onPointerDown={(e) => {
        drag.current = true;
        e.currentTarget.setPointerCapture(e.pointerId);
      }}
      onPointerMove={onMove}
      onPointerUp={() => (drag.current = false)}
      onKeyDown={(e) => {
        if (e.key === "ArrowLeft") setRatio(Math.max(0.3, ratio - 0.02));
        if (e.key === "ArrowRight") setRatio(Math.min(0.78, ratio + 0.02));
      }}
      className="group hidden cursor-col-resize items-stretch justify-center lg:flex lg:[grid-column:2] lg:[grid-row:1/-1]"
    >
      <span className="w-px bg-transparent transition-colors group-hover:bg-ring group-focus-visible:bg-ring" />
    </div>
  );
}
