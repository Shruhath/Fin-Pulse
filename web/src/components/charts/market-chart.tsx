"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import * as d3 from "d3";
import { gsap } from "gsap";
import { useGSAP } from "@gsap/react";

import { useFocus } from "@/components/overview/focus";
import type { EntityRow, EventMarker, MarketPoint } from "@/lib/api/types";
import { fmtDayLong, fmtInt, fmtScore } from "@/lib/format";

const HEIGHT = 320;
const M = { top: 14, right: 20, bottom: 58, left: 40 };
const LANE = 20; // event lane height, between the plot and the date axis

const day = (iso: string) => new Date(`${iso.slice(0, 10)}T00:00:00Z`);

interface Props {
  market: MarketPoint[];
  events: EventMarker[];
  entities: EntityRow[];
}

/**
 * Market sentiment: the daily mean of entity scores with a ±1σ band, on an
 * axis pinned to −1..1. The scale is never fitted to the data: a quiet week
 * must look quiet, and a split market must look split, not flat.
 */
export function MarketChart({ market, events, entities }: Props) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const [width, setWidth] = useState(0);
  const { entityId, day: focusDay, setFocus } = useFocus();

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => setWidth(Math.round(entry.contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const innerW = Math.max(width - M.left - M.right, 0);
  const innerH = HEIGHT - M.top - M.bottom;

  const scales = useMemo(() => {
    const x = d3
      .scaleUtc()
      .domain(d3.extent(market, (d) => day(d.t)) as [Date, Date])
      .range([0, innerW]);
    const y = d3.scaleLinear().domain([-1, 1]).range([innerH, 0]);
    return { x, y };
  }, [market, innerW, innerH]);

  // Static layers: grid, band, mean, events, axes. Redrawn on data or size change.
  useEffect(() => {
    const svg = svgRef.current;
    if (!svg || innerW <= 0 || market.length === 0) return;
    const { x, y } = scales;
    const root = d3.select(svg);
    root.selectAll("*").remove();

    const defs = root.append("defs");
    defs
      .append("clipPath")
      .attr("id", "mc-reveal")
      .append("rect")
      .attr("class", "mc-reveal-rect")
      .attr("x", 0)
      .attr("y", -M.top)
      .attr("width", innerW)
      .attr("height", HEIGHT);

    const g = root.append("g").attr("transform", `translate(${M.left},${M.top})`);

    // y grid + labels (pinned ticks)
    const yTicks = [-1, -0.5, 0, 0.5, 1];
    g.append("g")
      .attr("class", "fp-axis")
      .call(
        d3
          .axisLeft(y)
          .tickValues(yTicks)
          .tickSize(-innerW)
          .tickPadding(10)
          .tickFormat((v) => (v === 0 ? "0" : fmtScore(v as number).replace(".00", "").replace(/\.50$/, ".5"))),
      );
    g.append("line")
      .attr("x1", 0)
      .attr("x2", innerW)
      .attr("y1", y(0))
      .attr("y2", y(0))
      .attr("stroke", "var(--chart-zero)")
      .attr("stroke-width", 1);

    const plot = g.append("g").attr("clip-path", "url(#mc-reveal)").attr("class", "mc-plot");

    const band = d3
      .area<MarketPoint>()
      .x((d) => x(day(d.t)))
      .y0((d) => y(Math.max(-1, d.mean - d.std)))
      .y1((d) => y(Math.min(1, d.mean + d.std)))
      .curve(d3.curveMonotoneX);
    plot.append("path").datum(market).attr("d", band).attr("fill", "var(--chart-band)");

    const line = d3
      .line<MarketPoint>()
      .x((d) => x(day(d.t)))
      .y((d) => y(d.mean))
      .curve(d3.curveMonotoneX);
    plot
      .append("path")
      .datum(market)
      .attr("class", "mc-mean")
      .attr("d", line)
      .attr("fill", "none")
      .attr("stroke", "var(--chart-line)")
      .attr("stroke-width", 2)
      .attr("stroke-linejoin", "round");

    // focused-entity overlay and crosshair live in their own layers
    g.append("g").attr("class", "mc-entity");
    g.append("g").attr("class", "mc-cross").style("pointer-events", "none");

    // event lane
    const laneY = innerH + LANE / 2 + 2;
    g.append("line")
      .attr("x1", 0)
      .attr("x2", innerW)
      .attr("y1", innerH + LANE + 4)
      .attr("y2", innerH + LANE + 4)
      .attr("stroke", "var(--chart-grid)");
    g.append("g")
      .attr("class", "mc-events")
      .selectAll("path")
      .data(events)
      .join("path")
      .attr("class", "mc-event")
      .attr("d", d3.symbol(d3.symbolDiamond, 44)())
      .attr("transform", (d) => `translate(${x(day(d.t))},${laneY})`)
      .attr("fill", "var(--text-2)")
      .attr("stroke", "var(--surface)")
      .attr("stroke-width", 1.5)
      .style("cursor", "pointer")
      .on("pointerenter", (_, d) => setFocus({ entityId: d.entityId, day: d.t.slice(0, 10) }))
      .on("pointerleave", () => setFocus({ entityId: null, day: null }))
      .append("title")
      .text((d) => `${d.type}: ${d.entityName}`);

    // date axis
    const ticks = innerW < 480 ? 4 : innerW < 800 ? 6 : 8;
    g.append("g")
      .attr("class", "fp-axis")
      .attr("transform", `translate(0,${innerH + LANE + 4})`)
      .call(
        d3
          .axisBottom(x)
          .ticks(ticks)
          .tickSize(0)
          .tickPadding(10)
          .tickFormat((d) => d3.utcFormat("%-d %b")(d as Date)),
      );

    // pointer capture over the plot (not the event lane)
    g.append("rect")
      .attr("width", innerW)
      .attr("height", innerH)
      .attr("fill", "transparent")
      .on("pointermove", (event) => {
        const [px] = d3.pointer(event);
        const t = x.invert(px);
        const i = d3.bisector((d: MarketPoint) => day(d.t)).center(market, t);
        setFocus({ day: market[i].t.slice(0, 10) });
      })
      .on("pointerleave", () => setFocus({ day: null }));
    // setFocus is stable in behaviour; redrawing on its identity would loop
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [market, events, scales, innerW, innerH]);

  // Dynamic layer: crosshair, focused entity overlay, marker emphasis.
  useEffect(() => {
    const svg = svgRef.current;
    if (!svg || innerW <= 0) return;
    const { x, y } = scales;
    const root = d3.select(svg);

    const overlay = root.select<SVGGElement>(".mc-entity");
    overlay.selectAll("*").remove();
    const ent = entityId ? entities.find((e) => e.id === entityId) : undefined;
    if (ent) {
      const pts = ent.series.filter((p) => day(p.t) >= x.domain()[0]);
      overlay
        .append("path")
        .datum(pts)
        .attr(
          "d",
          d3
            .line<{ t: string; v: number }>()
            .x((d) => x(day(d.t)))
            .y((d) => y(d.v))
            .curve(d3.curveMonotoneX),
        )
        .attr("fill", "none")
        .attr("stroke", "var(--chart-focus-line)")
        .attr("stroke-width", 1.5)
        .attr("stroke-dasharray", "1 0")
        .attr("opacity", 0.9);
      const last = pts[pts.length - 1];
      if (last) {
        overlay
          .append("text")
          .attr("x", Math.min(x(day(last.t)) - 6, innerW - 6))
          .attr("y", y(last.v) - 8)
          .attr("text-anchor", "end")
          .attr("fill", "var(--text)")
          .attr("font-size", 11)
          .attr("font-weight", 600)
          .text(ent.name);
      }
    }

    root
      .selectAll<SVGPathElement, EventMarker>(".mc-event")
      .attr("fill", (d) => (entityId && d.entityId === entityId ? "var(--accent)" : "var(--text-2)"))
      .attr("opacity", (d) => (entityId && d.entityId !== entityId ? 0.35 : 1));

    const cross = root.select<SVGGElement>(".mc-cross");
    cross.selectAll("*").remove();
    const p = focusDay ? market.find((m) => m.t.slice(0, 10) === focusDay) : undefined;
    if (p) {
      const cx = x(day(p.t));
      cross
        .append("line")
        .attr("x1", cx)
        .attr("x2", cx)
        .attr("y1", 0)
        .attr("y2", innerH + LANE + 4)
        .attr("stroke", "var(--border-strong)");
      cross
        .append("circle")
        .attr("cx", cx)
        .attr("cy", y(p.mean))
        .attr("r", 4)
        .attr("fill", "var(--chart-line)")
        .attr("stroke", "var(--surface)")
        .attr("stroke-width", 2);
    }
  }, [entityId, focusDay, entities, market, scales, innerW, innerH]);

  // The one authored moment: the trace writes itself left to right, once.
  useGSAP(
    () => {
      if (innerW <= 0) return;
      const mm = gsap.matchMedia();
      mm.add("(prefers-reduced-motion: no-preference)", () => {
        gsap.fromTo(
          ".mc-reveal-rect",
          { attr: { width: 0 } },
          { attr: { width: innerW }, duration: 1.2, ease: "power3.out" },
        );
        gsap.from(".mc-event", { opacity: 0, duration: 0.4, stagger: 0.03, delay: 0.5, ease: "power2.out" });
      });
      return () => mm.revert();
    },
    { scope: wrapRef, dependencies: [market, innerW > 0] },
  );

  const focusPoint = focusDay ? market.find((m) => m.t.slice(0, 10) === focusDay) : undefined;
  const focusEntity = entityId ? entities.find((e) => e.id === entityId) : undefined;
  const focusEntityValue = focusEntity && focusDay ? focusEntity.series.find((s) => s.t.slice(0, 10) === focusDay)?.v : undefined;
  const focusEvents = focusDay ? events.filter((e) => e.t.slice(0, 10) === focusDay) : [];

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
    e.preventDefault();
    const i = focusDay ? market.findIndex((m) => m.t.slice(0, 10) === focusDay) : market.length;
    const next = Math.min(market.length - 1, Math.max(0, i + (e.key === "ArrowRight" ? 1 : -1)));
    setFocus({ day: market[next].t.slice(0, 10) });
  };

  const last = market[market.length - 1];
  const tooltipX = focusPoint ? M.left + scales.x(day(focusPoint.t)) : 0;

  return (
    <div ref={wrapRef} className="relative">
      <svg
        ref={svgRef}
        width={width}
        height={HEIGHT}
        role="img"
        tabIndex={0}
        onKeyDown={onKeyDown}
        onBlur={() => setFocus({ day: null })}
        aria-label={
          last
            ? `Market sentiment, daily mean of company scores on a scale from minus one to plus one. Latest ${fmtScore(last.mean)} with a spread of ${last.std.toFixed(2)}. Use the left and right arrow keys to read each day.`
            : "Market sentiment chart"
        }
        className="block overflow-visible rounded-s"
      />
      {focusPoint && (
        <div
          className="pointer-events-none absolute top-2 z-10 w-60 rounded-m border border-line bg-surface p-3 text-xs shadow-pop"
          style={{
            left: tooltipX > width - 260 ? undefined : tooltipX + 14,
            right: tooltipX > width - 260 ? width - tooltipX + 14 : undefined,
          }}
        >
          <p className="font-semibold text-ink">{fmtDayLong(focusPoint.t)}</p>
          <dl className="mt-2 grid grid-cols-[1fr_auto] gap-x-3 gap-y-1 text-ink-2">
            <dt>Market mean</dt>
            <dd className="num text-right font-semibold text-ink">{fmtScore(focusPoint.mean)}</dd>
            <dt>Spread (±1σ)</dt>
            <dd className="num text-right">{focusPoint.std.toFixed(2)}</dd>
            <dt>Scored mentions</dt>
            <dd className="num text-right">{fmtInt(focusPoint.n)}</dd>
            {focusEntity && focusEntityValue !== undefined && (
              <>
                <dt className="truncate">{focusEntity.name}</dt>
                <dd className="num text-right font-semibold text-ink">{fmtScore(focusEntityValue)}</dd>
              </>
            )}
          </dl>
          {focusEvents.length > 0 && (
            <ul className="mt-2 space-y-1 border-t border-line pt-2">
              {focusEvents.map((ev) => (
                <li key={ev.id} className="text-ink-2">
                  <span className="font-semibold text-ink">{ev.type}</span> · {ev.entityName}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
