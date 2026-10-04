"use client";

import { useEffect, useRef, useState } from "react";
import * as d3 from "d3";
import { gsap } from "gsap";
import { useGSAP } from "@gsap/react";

import { useFocus } from "@/components/linked/focus";
import type { EventGroup, EventRecord } from "@/lib/api/types";

export const GROUPS: EventGroup[] = ["Regulatory", "Insolvency", "Governance", "Corporate action", "Dividend"];
const M = { top: 8, right: 18, bottom: 28, left: 128 };
const day = (iso: string) => new Date(`${iso.slice(0, 10)}T00:00:00Z`);

// Shape carries sentiment as well as colour: triangle up, triangle down, circle.
const SHAPE = { positive: d3.symbolTriangle, negative: d3.symbolTriangle, neutral: d3.symbolCircle } as const;

/**
 * Events as swimlanes: one lane per event group, time across. Markers point up
 * for positive and down for negative, so the reading survives without colour.
 */
export function EventTimeline({
  events,
  selectedId,
  onSelect,
  windowDays,
}: {
  events: EventRecord[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  windowDays: number;
}) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const [size, setSize] = useState({ w: 0, h: 260 });
  const { entityId, setFocus } = useFocus();

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setSize({ w: Math.round(e.contentRect.width), h: Math.max(220, Math.round(e.contentRect.height)) }));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    const svg = svgRef.current;
    if (!svg || size.w === 0) return;
    const innerW = size.w - M.left - M.right;
    const innerH = size.h - M.top - M.bottom;
    const end = d3.max(events, (e) => day(e.t)) ?? new Date();
    const x = d3
      .scaleUtc()
      .domain([d3.utcDay.offset(end, -(windowDays - 1)), d3.utcDay.offset(end, 1)])
      .range([0, innerW]);
    const y = d3.scaleBand<EventGroup>().domain(GROUPS).range([0, innerH]).paddingInner(0.12);

    const root = d3.select(svg);
    root.selectAll("*").remove();
    const g = root.append("g").attr("transform", `translate(${M.left},${M.top})`);

    const lanes = g.append("g");
    lanes
      .selectAll("rect")
      .data(GROUPS)
      .join("rect")
      .attr("x", 0)
      .attr("y", (d) => y(d)!)
      .attr("width", innerW)
      .attr("height", y.bandwidth())
      .attr("fill", (_, i) => (i % 2 ? "var(--surface)" : "var(--surface-2)"));
    lanes
      .selectAll("text")
      .data(GROUPS)
      .join("text")
      .attr("x", -12)
      .attr("y", (d) => y(d)! + y.bandwidth() / 2)
      .attr("dy", "0.32em")
      .attr("text-anchor", "end")
      .attr("fill", "var(--text-2)")
      .attr("font-family", "var(--font-mono)")
      .attr("font-size", 11)
      .text((d) => d.toLowerCase());
    lanes
      .selectAll("text.count")
      .data(GROUPS)
      .join("text")
      .attr("class", "count")
      .attr("x", -12)
      .attr("y", (d) => y(d)! + y.bandwidth() / 2 + 14)
      .attr("text-anchor", "end")
      .attr("fill", "var(--text-3)")
      .attr("font-family", "var(--font-mono)")
      .attr("font-size", 10)
      .text((d) => `${events.filter((e) => e.group === d).length} events`);

    g.append("g")
      .attr("class", "fp-axis")
      .attr("transform", `translate(0,${innerH + 6})`)
      .call(d3.axisBottom(x).ticks(innerW < 500 ? 4 : 8).tickSize(0).tickPadding(6).tickFormat((d) => d3.utcFormat("%-d %b")(d as Date)));

    // jitter markers that share a lane and day so none hide behind another
    const seen = new Map<string, number>();
    const pos = events.map((e) => {
      const key = `${e.group}|${e.t.slice(0, 10)}`;
      const k = seen.get(key) ?? 0;
      seen.set(key, k + 1);
      const band = y.bandwidth();
      const offset = ((k % 3) - 1) * Math.min(14, band / 4);
      return { e, cx: x(day(e.t)) + x(d3.utcDay.offset(day(e.t), 1)) / 2 - x(day(e.t)) / 2, cy: y(e.group)! + band / 2 + offset };
    });

    g.append("g")
      .selectAll("path")
      .data(pos)
      .join("path")
      .attr("class", "et-mark")
      .attr("d", (p) => d3.symbol(SHAPE[p.e.sentiment], p.e.id === selectedId ? 150 : 80)())
      .attr("transform", (p) => `translate(${p.cx},${p.cy}) rotate(${p.e.sentiment === "negative" ? 180 : 0})`)
      .attr("fill", (p) => (p.e.sentiment === "positive" ? "var(--pos)" : p.e.sentiment === "negative" ? "var(--neg)" : "var(--neu)"))
      .attr("stroke", (p) => (p.e.id === selectedId ? "var(--focus-ring)" : "var(--surface)"))
      .attr("stroke-width", (p) => (p.e.id === selectedId ? 2.5 : 1.5))
      .attr("opacity", (p) => (entityId && p.e.entityId !== entityId ? 0.25 : 1))
      .attr("tabindex", 0)
      .attr("role", "button")
      .attr("aria-label", (p) => `${p.e.type}, ${p.e.entityName}, ${p.e.t.slice(0, 10)}`)
      .style("cursor", "pointer")
      .on("click", (_, p) => onSelect(p.e.id))
      .on("keydown", (ev: KeyboardEvent, p) => {
        if (ev.key === "Enter" || ev.key === " ") {
          ev.preventDefault();
          onSelect(p.e.id);
        }
      })
      .on("pointerenter", (_, p) => setFocus({ entityId: p.e.entityId }))
      .on("pointerleave", () => setFocus({ entityId: null }))
      .append("title")
      .text((p) => `${p.e.type} · ${p.e.entityName}\n${p.e.headline}`);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [events, selectedId, size, windowDays, entityId]);

  useGSAP(
    () => {
      const mm = gsap.matchMedia();
      mm.add("(prefers-reduced-motion: no-preference)", () => {
        gsap.from(".et-mark", { opacity: 0, duration: 0.45, stagger: { each: 0.015, from: "start" }, ease: "power2.out" });
      });
      return () => mm.revert();
    },
    { scope: wrapRef, dependencies: [events.length, size.w > 0] },
  );

  return (
    <div ref={wrapRef} className="relative h-full min-h-[220px]">
      <svg
        ref={svgRef}
        width={size.w}
        height={size.h}
        aria-label={`Event timeline, ${events.length} events in five lanes. Markers point up for positive and down for negative.`}
        className="absolute inset-0"
      />
    </div>
  );
}
