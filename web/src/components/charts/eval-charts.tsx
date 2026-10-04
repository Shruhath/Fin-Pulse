"use client";

import { useEffect, useRef, useState } from "react";
import * as d3 from "d3";
import { gsap } from "gsap";
import { useGSAP } from "@gsap/react";

import type { Confusion, MetricRow, ReliabilityBin } from "@/lib/api/types";

function useSize<T extends HTMLElement>(minH: number) {
  const ref = useRef<T>(null);
  const [size, setSize] = useState({ w: 0, h: minH });
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setSize({ w: Math.round(e.contentRect.width), h: Math.max(minH, Math.round(e.contentRect.height)) }));
    ro.observe(el);
    return () => ro.disconnect();
  }, [minH]);
  return [ref, size] as const;
}

/**
 * Macro-F1 per model as a dot plot: a circle for the public benchmark, a
 * diamond for the Indian gold slice, joined by a line. The line's length is
 * the transfer gap (RQ4). The x axis is fixed at 0.4–1.0 for every model.
 */
export function TransferPlot({ rows }: { rows: MetricRow[] }) {
  const [ref, size] = useSize<HTMLDivElement>(220);
  const svgRef = useRef<SVGSVGElement>(null);
  const models = [...new Set(rows.map((r) => r.model))];

  useEffect(() => {
    const svg = svgRef.current;
    if (!svg || size.w === 0) return;
    const M = { top: 28, right: 24, bottom: 34, left: Math.min(220, size.w * 0.38) };
    const innerW = size.w - M.left - M.right;
    const innerH = Math.min(size.h - M.top - M.bottom, models.length * 76);
    const x = d3.scaleLinear().domain([0.4, 1]).range([0, innerW]);
    const y = d3.scaleBand().domain(models).range([0, innerH]).padding(0.4);
    const root = d3.select(svg);
    root.selectAll("*").remove();
    const g = root.append("g").attr("transform", `translate(${M.left},${M.top})`);

    g.append("g").attr("class", "fp-axis").attr("transform", `translate(0,${innerH})`).call(d3.axisBottom(x).ticks(6).tickSize(-innerH).tickPadding(8));
    g.append("text").attr("x", innerW).attr("y", innerH + 30).attr("text-anchor", "end").attr("fill", "var(--text-3)").attr("font-size", 10.5).attr("font-family", "var(--font-mono)").text("macro-F1");

    for (const m of models) {
      const rs = rows.filter((r) => r.model === m);
      const baseline = rs[0]?.baseline;
      const cy = y(m)! + y.bandwidth() / 2;
      g.append("text")
        .attr("x", -14)
        .attr("y", cy)
        .attr("dy", "0.32em")
        .attr("text-anchor", "end")
        .attr("fill", baseline ? "var(--text-2)" : "var(--text)")
        .attr("font-weight", baseline ? 400 : 600)
        .attr("font-size", 12.5)
        .text(m);
      const vals = rs.map((r) => r.metrics.macroF1);
      const lo = d3.min(vals)!;
      const hi = d3.max(vals)!;
      g.append("line").attr("class", "tp-gap").attr("x1", x(lo)).attr("x2", x(hi)).attr("y1", cy).attr("y2", cy).attr("stroke", baseline ? "var(--border-strong)" : "var(--accent)").attr("stroke-width", 2);
      for (const r of rs) {
        g.append("path")
          .attr("class", "tp-dot")
          .attr("d", d3.symbol(r.indian ? d3.symbolDiamond : d3.symbolCircle, 90)())
          .attr("transform", `translate(${x(r.metrics.macroF1)},${cy})`)
          .attr("fill", r.indian ? "var(--accent)" : "var(--surface)")
          .attr("stroke", baseline ? "var(--text-2)" : "var(--accent)")
          .attr("stroke-width", 2)
          .append("title")
          .text(`${r.model} · ${r.dataset}: ${r.metrics.macroF1.toFixed(2)}`);
      }
      const gold = rs.find((r) => r.dataset === "FinPulse gold");
      const pub = rs.find((r) => !r.indian);
      if (gold && pub && !baseline) {
        g.append("text")
          .attr("x", (x(gold.metrics.macroF1) + x(pub.metrics.macroF1)) / 2)
          .attr("y", cy - 12)
          .attr("text-anchor", "middle")
          .attr("fill", "var(--accent-ink)")
          .attr("font-family", "var(--font-mono)")
          .attr("font-size", 10.5)
          .text(`gap −${(pub.metrics.macroF1 - gold.metrics.macroF1).toFixed(2)}`);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, size]);

  useGSAP(
    () => {
      const mm = gsap.matchMedia();
      mm.add("(prefers-reduced-motion: no-preference)", () => {
        gsap.from(".tp-gap", { scaleX: 0, transformOrigin: "left center", duration: 0.7, ease: "expo.out", stagger: 0.08 });
        gsap.from(".tp-dot", { opacity: 0, duration: 0.4, delay: 0.3, stagger: 0.03 });
      });
      return () => mm.revert();
    },
    { scope: ref, dependencies: [size.w > 0] },
  );

  return (
    <div className="flex h-full flex-col">
      <ul className="flex flex-wrap gap-x-4 gap-y-1 px-3 pt-2 font-mono text-2xs text-ink-3">
        <li className="flex items-center gap-1.5">
          <svg viewBox="0 0 10 10" className="size-2.5" aria-hidden="true">
            <circle cx="5" cy="5" r="3.6" fill="none" stroke="var(--accent)" strokeWidth="1.6" />
          </svg>
          public benchmark
        </li>
        <li className="flex items-center gap-1.5">
          <svg viewBox="0 0 10 10" className="size-2.5" aria-hidden="true">
            <path d="M5 .5 9.5 5 5 9.5.5 5Z" fill="var(--accent)" />
          </svg>
          Indian data (SEntFiN, FinPulse gold)
        </li>
        <li>bold rows are FinPulse models; grey rows are baselines</li>
      </ul>
      <div ref={ref} className="relative min-h-0 flex-1">
        <svg ref={svgRef} width={size.w} height={size.h} role="img" aria-label="Entity sentiment macro-F1 by model on public and Indian datasets" className="absolute inset-0" />
      </div>
    </div>
  );
}

/** Confusion matrix, row-normalised: each cell's shade is the share of its gold row. */
export function ConfusionMatrix({ data }: { data: Confusion }) {
  const [ref, size] = useSize<HTMLDivElement>(200);
  const svgRef = useRef<SVGSVGElement>(null);
  useEffect(() => {
    const svg = svgRef.current;
    if (!svg || size.w === 0) return;
    const M = { top: 34, right: 12, bottom: 12, left: 86 };
    const side = Math.min(size.w - M.left - M.right, size.h - M.top - M.bottom);
    const n = data.labels.length;
    const cell = side / n;
    const root = d3.select(svg);
    root.selectAll("*").remove();
    const g = root.append("g").attr("transform", `translate(${M.left + (size.w - M.left - M.right - side) / 2},${M.top})`);
    data.matrix.forEach((row, i) => {
      const total = d3.sum(row) || 1;
      row.forEach((v, j) => {
        const share = v / total;
        g.append("rect").attr("x", j * cell).attr("y", i * cell).attr("width", cell - 2).attr("height", cell - 2).attr("fill", "var(--accent)").attr("fill-opacity", 0.08 + share * 0.92);
        g.append("text")
          .attr("x", j * cell + cell / 2)
          .attr("y", i * cell + cell / 2)
          .attr("text-anchor", "middle")
          .attr("dy", "-0.1em")
          .attr("fill", share > 0.55 ? "var(--text-inverse)" : "var(--text)")
          .attr("font-family", "var(--font-mono)")
          .attr("font-size", Math.max(11, cell / 6))
          .attr("font-weight", 600)
          .text(v);
        g.append("text")
          .attr("x", j * cell + cell / 2)
          .attr("y", i * cell + cell / 2)
          .attr("text-anchor", "middle")
          .attr("dy", "1.3em")
          .attr("fill", share > 0.55 ? "var(--text-inverse)" : "var(--text-3)")
          .attr("font-family", "var(--font-mono)")
          .attr("font-size", 10)
          .text(`${Math.round(share * 100)}%`);
      });
      g.append("text").attr("x", -10).attr("y", i * cell + cell / 2).attr("dy", "0.32em").attr("text-anchor", "end").attr("fill", "var(--text-2)").attr("font-size", 11.5).text(data.labels[i]);
    });
    data.labels.forEach((l, j) =>
      g.append("text").attr("x", j * cell + cell / 2).attr("y", -10).attr("text-anchor", "middle").attr("fill", "var(--text-2)").attr("font-size", 11.5).text(l),
    );
    g.append("text").attr("x", -10).attr("y", -10).attr("text-anchor", "end").attr("fill", "var(--text-3)").attr("font-family", "var(--font-mono)").attr("font-size", 10).text("gold ↓ / pred →");
  }, [data, size]);
  return (
    <div ref={ref} className="relative h-full min-h-[200px]">
      <svg ref={svgRef} width={size.w} height={size.h} role="img" aria-label={`Confusion matrix for ${data.model} on ${data.dataset}`} className="absolute inset-0" />
    </div>
  );
}

/** Reliability diagram: accuracy per confidence bin before and after temperature scaling. */
export function Reliability({ before, after, eceBefore, eceAfter }: { before: ReliabilityBin[]; after: ReliabilityBin[]; eceBefore: number; eceAfter: number }) {
  const [ref, size] = useSize<HTMLDivElement>(200);
  const svgRef = useRef<SVGSVGElement>(null);
  useEffect(() => {
    const svg = svgRef.current;
    if (!svg || size.w === 0) return;
    const M = { top: 10, right: 14, bottom: 34, left: 40 };
    const side = Math.min(size.w - M.left - M.right, size.h - M.top - M.bottom);
    const x = d3.scaleLinear().domain([0.3, 1]).range([0, side]);
    const y = d3.scaleLinear().domain([0.3, 1]).range([side, 0]);
    const root = d3.select(svg);
    root.selectAll("*").remove();
    const g = root.append("g").attr("transform", `translate(${M.left},${M.top})`);
    g.append("g").attr("class", "fp-axis").attr("transform", `translate(0,${side})`).call(d3.axisBottom(x).ticks(4).tickSize(-side).tickPadding(6));
    g.append("g").attr("class", "fp-axis").call(d3.axisLeft(y).ticks(4).tickSize(-side).tickPadding(6));
    g.append("line").attr("x1", x(0.3)).attr("y1", y(0.3)).attr("x2", x(1)).attr("y2", y(1)).attr("stroke", "var(--chart-zero)").attr("stroke-dasharray", "3 3");
    const line = d3.line<ReliabilityBin>().x((d) => x(d.confidence)).y((d) => y(d.accuracy));
    g.append("path").datum(before).attr("d", line).attr("fill", "none").attr("stroke", "var(--text-3)").attr("stroke-width", 1.5);
    g.append("path").datum(after).attr("d", line).attr("fill", "none").attr("stroke", "var(--accent)").attr("stroke-width", 2);
    g.selectAll("circle.b").data(before).join("circle").attr("cx", (d) => x(d.confidence)).attr("cy", (d) => y(d.accuracy)).attr("r", 3).attr("fill", "var(--surface)").attr("stroke", "var(--text-3)");
    g.selectAll("circle.a").data(after).join("circle").attr("cx", (d) => x(d.confidence)).attr("cy", (d) => y(d.accuracy)).attr("r", 3.5).attr("fill", "var(--accent)");
    g.append("text").attr("x", side).attr("y", side + 30).attr("text-anchor", "end").attr("fill", "var(--text-3)").attr("font-family", "var(--font-mono)").attr("font-size", 10).text("confidence → accuracy ↑");
  }, [before, after, size]);
  return (
    <div className="flex h-full flex-col">
      <ul className="flex flex-wrap gap-x-4 px-3 pt-2 font-mono text-2xs text-ink-3">
        <li className="flex items-center gap-1.5">
          <span className="h-px w-4 bg-ink-3" aria-hidden="true" /> before · ECE {eceBefore.toFixed(3)}
        </li>
        <li className="flex items-center gap-1.5">
          <span className="h-0.5 w-4 bg-accent" aria-hidden="true" /> after temperature scaling · ECE {eceAfter.toFixed(3)}
        </li>
      </ul>
      <div ref={ref} className="relative min-h-0 flex-1">
        <svg ref={svgRef} width={size.w} height={size.h} role="img" aria-label={`Reliability diagram. ECE ${eceBefore.toFixed(3)} before and ${eceAfter.toFixed(3)} after calibration.`} className="absolute inset-0" />
      </div>
    </div>
  );
}
