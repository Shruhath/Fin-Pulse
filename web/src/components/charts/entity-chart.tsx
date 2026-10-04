"use client";

import { useEffect, useRef, useState } from "react";
import * as d3 from "d3";
import { gsap } from "gsap";
import { useGSAP } from "@gsap/react";

import { useFocus } from "@/components/linked/focus";
import type { EventRecord, SeriesPoint } from "@/lib/api/types";
import { fmtDayLong, fmtScore } from "@/lib/format";

const M = { top: 12, right: 16, bottom: 48, left: 38 };
const day = (iso: string) => new Date(`${iso.slice(0, 10)}T00:00:00Z`);

/**
 * One company's sentiment over the window on the pinned −1..1 scale. The area
 * above zero fills green and below zero red, so the reading never depends on
 * colour alone: position against the zero line carries it too.
 */
export function EntityChart({ series, events, name }: { series: SeriesPoint[]; events: EventRecord[]; name: string }) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const [size, setSize] = useState({ w: 0, h: 240 });
  const [hover, setHover] = useState<SeriesPoint | null>(null);
  const { setFocus } = useFocus();

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setSize({ w: Math.round(e.contentRect.width), h: Math.max(200, Math.round(e.contentRect.height)) }));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const innerW = Math.max(size.w - M.left - M.right, 0);
  const innerH = size.h - M.top - M.bottom;
  const x = d3.scaleUtc().domain(d3.extent(series, (d) => day(d.t)) as [Date, Date]).range([0, innerW]);
  const y = d3.scaleLinear().domain([-1, 1]).range([innerH, 0]);

  useEffect(() => {
    const svg = svgRef.current;
    if (!svg || innerW <= 0 || series.length < 2) return;
    const root = d3.select(svg);
    root.selectAll("*").remove();
    const uid = name.replace(/\W/g, "");
    const defs = root.append("defs");
    defs.append("clipPath").attr("id", `ec-above-${uid}`).append("rect").attr("width", innerW).attr("height", y(0));
    defs.append("clipPath").attr("id", `ec-below-${uid}`).append("rect").attr("y", y(0)).attr("width", innerW).attr("height", innerH - y(0));
    defs.append("clipPath").attr("id", `ec-reveal-${uid}`).append("rect").attr("class", "ec-reveal").attr("width", innerW).attr("height", innerH);

    const g = root.append("g").attr("transform", `translate(${M.left},${M.top})`);
    g.append("g")
      .attr("class", "fp-axis")
      .call(d3.axisLeft(y).tickValues([-1, -0.5, 0, 0.5, 1]).tickSize(-innerW).tickPadding(8).tickFormat((v) => (v === 0 ? "0" : fmtScore(v as number).replace(".00", "").replace(/\.50$/, ".5"))));
    g.append("line").attr("x1", 0).attr("x2", innerW).attr("y1", y(0)).attr("y2", y(0)).attr("stroke", "var(--chart-zero)");

    const area = d3.area<SeriesPoint>().x((d) => x(day(d.t))).y0(y(0)).y1((d) => y(d.v)).curve(d3.curveMonotoneX);
    const plot = g.append("g").attr("clip-path", `url(#ec-reveal-${uid})`);
    plot.append("path").datum(series).attr("d", area).attr("fill", "var(--pos-weak)").attr("clip-path", `url(#ec-above-${uid})`);
    plot.append("path").datum(series).attr("d", area).attr("fill", "var(--neg-weak)").attr("clip-path", `url(#ec-below-${uid})`);
    plot
      .append("path")
      .datum(series)
      .attr("d", d3.line<SeriesPoint>().x((d) => x(day(d.t))).y((d) => y(d.v)).curve(d3.curveMonotoneX))
      .attr("fill", "none")
      .attr("stroke", "var(--text)")
      .attr("stroke-width", 1.6);

    const lane = innerH + 14;
    g.append("g")
      .selectAll("path")
      .data(events.filter((e) => day(e.t) >= x.domain()[0]))
      .join("path")
      .attr("class", "ec-event")
      .attr("d", d3.symbol(d3.symbolDiamond, 48)())
      .attr("transform", (d) => `translate(${x(day(d.t))},${lane})`)
      .attr("fill", (d) => (d.sentiment === "negative" ? "var(--neg)" : d.sentiment === "positive" ? "var(--pos)" : "var(--neu)"))
      .attr("stroke", "var(--surface)")
      .attr("stroke-width", 1.5)
      .append("title")
      .text((d) => `${d.type}: ${d.headline}`);

    g.append("g")
      .attr("class", "fp-axis")
      .attr("transform", `translate(0,${innerH + 26})`)
      .call(d3.axisBottom(x).ticks(innerW < 420 ? 3 : 6).tickSize(0).tickPadding(6).tickFormat((d) => d3.utcFormat("%-d %b")(d as Date)));

    g.append("g").attr("class", "ec-cross");
    g.append("rect")
      .attr("width", innerW)
      .attr("height", innerH)
      .attr("fill", "transparent")
      .on("pointermove", (ev) => {
        const i = d3.bisector((d: SeriesPoint) => day(d.t)).center(series, x.invert(d3.pointer(ev)[0]));
        setHover(series[i]);
        setFocus({ day: series[i].t.slice(0, 10) });
      })
      .on("pointerleave", () => {
        setHover(null);
        setFocus({ day: null });
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [series, events, innerW, innerH, name]);

  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;
    const cross = d3.select(svg).select<SVGGElement>(".ec-cross");
    cross.selectAll("*").remove();
    if (!hover) return;
    const cx = x(day(hover.t));
    cross.append("line").attr("x1", cx).attr("x2", cx).attr("y1", 0).attr("y2", innerH).attr("stroke", "var(--border-strong)");
    cross.append("circle").attr("cx", cx).attr("cy", y(hover.v)).attr("r", 3.5).attr("fill", "var(--accent)").attr("stroke", "var(--surface)").attr("stroke-width", 2);
  }, [hover, x, y, innerH]);

  useGSAP(
    () => {
      if (innerW <= 0) return;
      const mm = gsap.matchMedia();
      mm.add("(prefers-reduced-motion: no-preference)", () => {
        gsap.fromTo(".ec-reveal", { attr: { width: 0 } }, { attr: { width: innerW }, duration: 1, ease: "power3.out" });
      });
      return () => mm.revert();
    },
    { scope: wrapRef, dependencies: [series, innerW > 0] },
  );

  const last = series[series.length - 1];
  return (
    <div ref={wrapRef} className="relative h-full min-h-[200px]">
      <svg
        ref={svgRef}
        width={size.w}
        height={size.h}
        role="img"
        aria-label={last ? `${name} sentiment over the window on a scale from minus one to plus one. Latest ${fmtScore(last.v)}.` : `${name} sentiment`}
        className="absolute inset-0"
      />
      {hover && (
        <p className="pointer-events-none absolute top-1 right-2 border border-line-strong bg-surface px-2 py-1 font-mono text-2xs text-ink-2">
          {fmtDayLong(hover.t)} · <span className="font-semibold text-ink">{fmtScore(hover.v)}</span>
        </p>
      )}
    </div>
  );
}
