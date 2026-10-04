"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import * as d3 from "d3";
import { gsap } from "gsap";
import { useGSAP } from "@gsap/react";
import { useTheme } from "next-themes";

import { useFocus } from "@/components/linked/focus";
import type { EntityRow, EventMarker, MarketPoint } from "@/lib/api/types";
import { fmtDayLong, fmtScore } from "@/lib/format";

const STRIP_H = 56; // market mean strip
const STRIP_GAP = 14;
const AXIS_H = 24;
const SCORE_W = 64;
const MIN_ROW = 13;

const dayKey = (iso: string) => iso.slice(0, 10);
const asDate = (k: string) => new Date(`${k}T00:00:00Z`);

function cssVar(name: string) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

interface Cell {
  row: number;
  col: number;
  v: number | null;
}

/**
 * The market as a grid: one row per company, one column per day, each cell
 * coloured on a fixed diverging scale from −1 (coral) through neutral to +1
 * (blue). The scale never refits, so a quiet window stays grey and a split one
 * shows both colours at once. Above it, the market mean with its ±1σ spread on
 * the same fixed scale. Events are outlined on the exact company and day.
 */
export function MarketHeatmap({ market, entities, events }: { market: MarketPoint[]; entities: EntityRow[]; events: EventMarker[] }) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const [size, setSize] = useState({ w: 0, h: 0 });
  const [cursor, setCursor] = useState<{ row: number; col: number } | null>(null);
  const { entityId, day, setFocus } = useFocus();
  const { resolvedTheme } = useTheme();
  const router = useRouter();

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setSize({ w: Math.round(e.contentRect.width), h: Math.round(e.contentRect.height) }));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const days = useMemo(() => market.map((m) => dayKey(m.t)), [market]);
  const rows = useMemo(() => [...entities].sort((a, b) => b.score - a.score), [entities]);
  const eventAt = useMemo(() => {
    const m = new Map<string, EventMarker[]>();
    for (const e of events) {
      const k = `${e.entityId}|${dayKey(e.t)}`;
      m.set(k, [...(m.get(k) ?? []), e]);
    }
    return m;
  }, [events]);

  const labelW = Math.min(184, Math.max(110, size.w * 0.2));
  const gridW = Math.max(0, size.w - labelW - SCORE_W - 12);
  const gridTop = STRIP_H + STRIP_GAP;
  const rowH = Math.max(MIN_ROW, (size.h - gridTop - AXIS_H) / Math.max(rows.length, 1));
  const gridH = rowH * rows.length;
  const totalH = gridTop + gridH + AXIS_H;
  const colW = gridW / Math.max(days.length, 1);

  // Static layers, redrawn on data, size or theme change.
  useEffect(() => {
    const svg = svgRef.current;
    if (!svg || gridW <= 0 || rows.length === 0 || days.length === 0) return;
    const color = d3
      .scaleDiverging<string>()
      .domain([-1, 0, 1])
      .interpolator(d3.piecewise(d3.interpolateLab, [cssVar("--neg"), cssVar("--div-mid"), cssVar("--pos")]))
      .clamp(true);
    const root = d3.select(svg);
    root.selectAll("*").remove();
    const g = root.append("g").attr("transform", `translate(${labelW},0)`);

    // -- market strip: mean and ±1σ on the same fixed −1..1 scale
    const x = d3.scaleBand<string>().domain(days).range([0, gridW]);
    const cx = (k: string) => x(k)! + x.bandwidth() / 2;
    const sy = d3.scaleLinear().domain([-1, 1]).range([STRIP_H - 4, 4]);
    const strip = g.append("g").attr("class", "hm-strip");
    strip.append("rect").attr("width", gridW).attr("height", STRIP_H).attr("fill", "var(--surface-2)");
    strip.append("line").attr("x1", 0).attr("x2", gridW).attr("y1", sy(0)).attr("y2", sy(0)).attr("stroke", "var(--chart-zero)");
    strip
      .append("path")
      .datum(market)
      .attr(
        "d",
        d3
          .area<MarketPoint>()
          .x((d) => cx(dayKey(d.t)))
          .y0((d) => sy(Math.max(-1, d.mean - d.std)))
          .y1((d) => sy(Math.min(1, d.mean + d.std)))
          .curve(d3.curveMonotoneX),
      )
      .attr("fill", "var(--text-3)")
      .attr("fill-opacity", 0.22);
    strip
      .append("path")
      .datum(market)
      .attr(
        "d",
        d3
          .line<MarketPoint>()
          .x((d) => cx(dayKey(d.t)))
          .y((d) => sy(d.mean))
          .curve(d3.curveMonotoneX),
      )
      .attr("fill", "none")
      .attr("stroke", "var(--chart-line)")
      .attr("stroke-width", 2);
    // strip labels sit in the gutters, in text ink
    root
      .append("text")
      .attr("x", labelW - 10)
      .attr("y", 18)
      .attr("text-anchor", "end")
      .attr("fill", "var(--text-2)")
      .attr("font-family", "var(--font-mono)")
      .attr("font-size", 10.5)
      .text("market mean");
    root
      .append("text")
      .attr("x", labelW - 10)
      .attr("y", 32)
      .attr("text-anchor", "end")
      .attr("fill", "var(--text-3)")
      .attr("font-family", "var(--font-mono)")
      .attr("font-size", 10)
      .text("±1σ, scale −1…+1");
    const last = market[market.length - 1];
    root
      .append("text")
      .attr("x", labelW + gridW + 10)
      .attr("y", sy(last.mean) + 4)
      .attr("fill", "var(--text)")
      .attr("font-family", "var(--font-mono)")
      .attr("font-size", 11)
      .attr("font-weight", 600)
      .text(fmtScore(last.mean));

    // -- the grid
    const grid = g.append("g").attr("transform", `translate(0,${gridTop})`);
    const cells: Cell[][] = days.map((k, col) =>
      rows.map((e, row) => {
        const p = e.series.find((s) => dayKey(s.t) === k);
        return { row, col, v: p ? p.v : null };
      }),
    );
    // rows always keep a 1px surface gap; columns drop theirs when dense, so 90 days don't stripe
    const colGap = colW >= 12 ? 1 : 0;
    const rowGap = 1;
    grid
      .selectAll<SVGGElement, Cell[]>("g.hm-col")
      .data(cells)
      .join("g")
      .attr("class", "hm-col")
      .selectAll("rect")
      .data((d) => d)
      .join("rect")
      .attr("x", (d) => d.col * colW)
      .attr("y", (d) => d.row * rowH)
      .attr("width", Math.max(colW - colGap, 0.5) + (colGap ? 0 : 0.4))
      .attr("height", Math.max(rowH - rowGap, 1))
      .attr("fill", (d) => (d.v === null ? "var(--surface-2)" : color(d.v)));

    // events: an accent outline on the exact company-day cell
    const marks: { row: number; col: number }[] = [];
    rows.forEach((e, row) =>
      days.forEach((k, col) => {
        if (eventAt.has(`${e.id}|${k}`)) marks.push({ row, col });
      }),
    );
    grid
      .append("g")
      .selectAll("rect")
      .data(marks)
      .join("rect")
      .attr("class", "hm-event")
      .attr("x", (d) => d.col * colW + 1)
      .attr("y", (d) => d.row * rowH + 1)
      .attr("width", Math.max(colW - colGap - 2, 2))
      .attr("height", Math.max(rowH - rowGap - 2, 1))
      .attr("fill", "none")
      .attr("stroke", "var(--focus-ring)")
      .attr("stroke-width", 1.5);

    // company labels (left) and window score (right), in text ink
    root
      .append("g")
      .attr("class", "hm-labels")
      .selectAll("text")
      .data(rows)
      .join("text")
      .attr("x", labelW - 10)
      .attr("y", (_, i) => gridTop + i * rowH + rowH / 2)
      .attr("dy", "0.34em")
      .attr("text-anchor", "end")
      .attr("fill", "var(--text-2)")
      .attr("font-size", Math.min(12.5, rowH - 2))
      .text((e) => (e.name.length * 6.6 > labelW - 14 ? `${e.name.slice(0, Math.floor((labelW - 14) / 6.6) - 1)}…` : e.name));
    const scores = root.append("g").attr("class", "hm-scores");
    rows.forEach((e, i) => {
      const y = gridTop + i * rowH + rowH / 2;
      const up = e.score > 0.12;
      const down = e.score < -0.12;
      const gx = labelW + gridW + 10;
      // icon carries the sign so the number never relies on colour alone
      scores
        .append("path")
        .attr("d", up ? "M0 4 4 -2 8 4Z" : down ? "M0 -2 4 4 8 -2Z" : "M0 0.5h8v1.5H0Z")
        .attr("transform", `translate(${gx},${y - 1})`)
        .attr("fill", up ? "var(--pos)" : down ? "var(--neg)" : "var(--neu)");
      scores
        .append("text")
        .attr("x", gx + 12)
        .attr("y", y)
        .attr("dy", "0.34em")
        .attr("fill", "var(--text)")
        .attr("font-family", "var(--font-mono)")
        .attr("font-size", Math.min(11, rowH - 2))
        .text(fmtScore(e.score));
    });

    // date axis
    const ticks = d3.utcDay.every(Math.max(1, Math.ceil(days.length / Math.max(3, Math.floor(gridW / 70)))));
    const tickKeys = new Set((ticks ? ticks.range(asDate(days[0]), d3.utcDay.offset(asDate(days[days.length - 1]), 1)) : []).map((d) => d.toISOString().slice(0, 10)));
    // drop any label that would sit within 48px of the previous one
    const labels: string[] = [];
    for (const k of days.filter((d) => tickKeys.has(d))) {
      if (!labels.length || cx(k) - cx(labels[labels.length - 1]) >= 48) labels.push(k);
    }
    g.append("g")
      .attr("transform", `translate(0,${gridTop + gridH + 16})`)
      .selectAll("text")
      .data(labels)
      .join("text")
      .attr("x", (k) => cx(k))
      .attr("text-anchor", "middle")
      .attr("fill", "var(--text-3)")
      .attr("font-family", "var(--font-mono)")
      .attr("font-size", 10.5)
      .text((k) => d3.utcFormat("%-d %b")(asDate(k)));

    g.append("g").attr("class", "hm-cursor").style("pointer-events", "none");
  }, [market, rows, days, eventAt, gridW, labelW, gridTop, gridH, rowH, colW, resolvedTheme]);

  // Dynamic layer: crosshair for the hovered cell, row and column from linked focus.
  useEffect(() => {
    const svg = svgRef.current;
    if (!svg || gridW <= 0) return;
    const layer = d3.select(svg).select<SVGGElement>(".hm-cursor");
    layer.selectAll("*").remove();
    const row = cursor?.row ?? (entityId ? rows.findIndex((e) => e.id === entityId) : -1);
    const col = cursor?.col ?? (day ? days.indexOf(day) : -1);
    if (row >= 0) {
      layer
        .append("rect")
        .attr("x", -labelW + 4)
        .attr("y", gridTop + row * rowH - 1)
        .attr("width", labelW + gridW + SCORE_W)
        .attr("height", rowH + 1)
        .attr("fill", "none")
        .attr("stroke", "var(--text-2)")
        .attr("stroke-width", 1);
    }
    if (col >= 0) {
      layer
        .append("rect")
        .attr("x", col * colW - 0.5)
        .attr("y", 0)
        .attr("width", colW)
        .attr("height", gridTop + gridH)
        .attr("fill", "none")
        .attr("stroke", "var(--text-2)")
        .attr("stroke-width", 1);
    }
    d3.select(svg)
      .selectAll<SVGTextElement, EntityRow>(".hm-labels text")
      .attr("fill", (_, i) => (i === row ? "var(--text)" : "var(--text-2)"))
      .attr("font-weight", (_, i) => (i === row ? 600 : 400));
  }, [cursor, entityId, day, rows, days, gridW, labelW, gridTop, gridH, rowH, colW]);

  // One authored moment: the grid fills in day by day, left to right.
  useGSAP(
    () => {
      if (gridW <= 0) return;
      const mm = gsap.matchMedia();
      mm.add("(prefers-reduced-motion: no-preference)", () => {
        gsap.from(".hm-col", { opacity: 0, duration: 0.35, stagger: { each: 0.9 / Math.max(days.length, 1) }, ease: "power2.out" });
        gsap.from(".hm-strip", { opacity: 0, duration: 0.6, ease: "power2.out" });
      });
      return () => mm.revert();
    },
    { scope: wrapRef, dependencies: [market, gridW > 0] },
  );

  const hit = (ev: React.PointerEvent<SVGSVGElement>) => {
    const r = ev.currentTarget.getBoundingClientRect();
    const px = ev.clientX - r.left - labelW;
    const py = ev.clientY - r.top;
    if (px < 0 || px > gridW) return null;
    const col = Math.min(days.length - 1, Math.max(0, Math.floor(px / colW)));
    if (py < gridTop) return { row: -1, col };
    const row = Math.floor((py - gridTop) / rowH);
    return row >= 0 && row < rows.length ? { row, col } : null;
  };

  const onMove = (ev: React.PointerEvent<SVGSVGElement>) => {
    const h = hit(ev);
    if (!h) return onLeave();
    setCursor(h.row >= 0 ? h : { row: -1, col: h.col });
    setFocus({ entityId: h.row >= 0 ? rows[h.row].id : null, day: days[h.col] });
  };
  const onLeave = () => {
    setCursor(null);
    setFocus({ entityId: null, day: null });
  };

  const onKey = (e: React.KeyboardEvent) => {
    const c = cursor && cursor.row >= 0 ? cursor : { row: 0, col: days.length - 1 };
    let { row, col } = c;
    if (e.key === "ArrowLeft") col = Math.max(0, col - 1);
    else if (e.key === "ArrowRight") col = Math.min(days.length - 1, col + 1);
    else if (e.key === "ArrowUp") row = Math.max(0, row - 1);
    else if (e.key === "ArrowDown") row = Math.min(rows.length - 1, row + 1);
    else if (e.key === "Enter" && cursor && cursor.row >= 0) return router.push(`/companies/${rows[cursor.row].id}`);
    else return;
    e.preventDefault();
    setCursor({ row, col });
    setFocus({ entityId: rows[row].id, day: days[col] });
  };

  // tooltip content
  const tip = cursor ? (() => {
    const k = days[cursor.col];
    const m = market[cursor.col];
    const ent = cursor.row >= 0 ? rows[cursor.row] : null;
    const v = ent ? ent.series.find((s) => dayKey(s.t) === k)?.v : undefined;
    const evs = ent ? eventAt.get(`${ent.id}|${k}`) ?? [] : events.filter((e) => dayKey(e.t) === k);
    return { k, m, ent, v, evs };
  })() : null;
  const tipLeft = cursor ? labelW + cursor.col * colW + colW + 12 : 0;
  const tipFlip = tipLeft > size.w - 260;
  const tipTop = cursor && cursor.row >= 0 ? Math.min(gridTop + cursor.row * rowH, Math.max(0, totalH - 160)) : 4;

  return (
    <div ref={wrapRef} className="relative h-full min-h-[340px] overflow-y-auto">
      <svg
        ref={svgRef}
        width={size.w}
        height={Math.max(totalH, 0)}
        tabIndex={0}
        role="img"
        aria-label={`Company sentiment heatmap: ${rows.length} companies by ${days.length} days on a fixed scale from minus one to plus one, with the market mean above. Arrow keys move between cells; Enter opens the company.`}
        onPointerMove={onMove}
        onPointerLeave={onLeave}
        onClick={() => cursor && cursor.row >= 0 && router.push(`/companies/${rows[cursor.row].id}`)}
        onKeyDown={onKey}
        onBlur={onLeave}
        className="block cursor-crosshair outline-none focus-visible:outline-1 focus-visible:outline-ring"
      />
      {tip && (
        <div
          className="pointer-events-none absolute z-10 w-56 border border-line-strong bg-surface p-2.5 text-xs shadow-pop"
          style={{ top: tipTop, left: tipFlip ? undefined : tipLeft, right: tipFlip ? size.w - (tipLeft - colW - 24) : undefined }}
        >
          <p className="font-mono text-2xs font-semibold text-accent-ink">{fmtDayLong(tip.k)}</p>
          <dl className="mt-1.5 grid grid-cols-[1fr_auto] gap-x-3 gap-y-1 text-ink-2">
            {tip.ent && (
              <>
                <dt className="truncate font-medium text-ink">{tip.ent.name}</dt>
                <dd className="text-right font-mono font-semibold text-ink">{tip.v === undefined ? "no reading" : fmtScore(tip.v)}</dd>
              </>
            )}
            <dt>market mean</dt>
            <dd className="text-right font-mono">{fmtScore(tip.m.mean)}</dd>
            <dt>spread ±1σ</dt>
            <dd className="text-right font-mono">{tip.m.std.toFixed(2)}</dd>
          </dl>
          {tip.evs.length > 0 && (
            <ul className="mt-2 space-y-1 border-t border-line pt-2">
              {tip.evs.slice(0, 3).map((e) => (
                <li key={e.id} className="text-ink-2">
                  <span className="font-semibold text-accent-ink">{e.type}</span>
                  {!tip.ent && <> · {e.entityName}</>}
                </li>
              ))}
            </ul>
          )}
          {tip.ent && <p className="mt-2 font-mono text-[10px] text-ink-3">click to open the company</p>}
        </div>
      )}
      <table className="sr-only">
        <caption>Company sentiment over the window</caption>
        <thead>
          <tr>
            <th scope="col">Company</th>
            <th scope="col">Window score</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((e) => (
            <tr key={e.id}>
              <th scope="row">{e.name}</th>
              <td>{fmtScore(e.score)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Legend for the tile header: the fixed diverging scale and the event outline. */
export function HeatmapLegend() {
  return (
    <span className="hidden items-center gap-3 font-mono sm:flex">
      <span className="flex items-center gap-1.5">
        −1
        <span
          className="h-2 w-24"
          style={{ background: "linear-gradient(90deg, var(--neg), var(--div-mid) 50%, var(--pos))" }}
          aria-hidden="true"
        />
        +1
      </span>
      <span className="flex items-center gap-1.5">
        <span className="size-2.5 border-[1.5px] border-ring" aria-hidden="true" />
        event
      </span>
    </span>
  );
}
