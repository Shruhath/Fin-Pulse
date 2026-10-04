"use client";

import { useEffect, useRef } from "react";
import * as d3 from "d3";
import { useTheme } from "next-themes";

/**
 * Desktop wallpaper drawn from the market itself: contour isolines of company
 * sentiment (rows sorted by latest score) across the last 90 days. It only
 * shows in the gaps between windows. With no data, the desktop stays plain.
 */
export function Wallpaper({ matrix }: { matrix: number[][] | null }) {
  const ref = useRef<HTMLCanvasElement>(null);
  const { resolvedTheme } = useTheme();

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas || !matrix || matrix.length < 2) return;
    const draw = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const w = window.innerWidth;
      const h = window.innerHeight;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;
      const ctx = canvas.getContext("2d")!;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);

      // upsample the rows × days grid so the isolines read as terrain
      const rows = matrix.length;
      const cols = matrix[0].length;
      const gw = 160;
      const gh = 90;
      const values = new Float64Array(gw * gh);
      for (let j = 0; j < gh; j++) {
        const fy = (j / (gh - 1)) * (rows - 1);
        const y0 = Math.floor(fy);
        const y1 = Math.min(rows - 1, y0 + 1);
        for (let i = 0; i < gw; i++) {
          const fx = (i / (gw - 1)) * (cols - 1);
          const x0 = Math.floor(fx);
          const x1 = Math.min(cols - 1, x0 + 1);
          const a = matrix[y0][x0] + (matrix[y0][x1] - matrix[y0][x0]) * (fx - x0);
          const b = matrix[y1][x0] + (matrix[y1][x1] - matrix[y1][x0]) * (fx - x0);
          values[j * gw + i] = a + (b - a) * (fy - y0);
        }
      }
      const styles = getComputedStyle(document.documentElement);
      const ink = styles.getPropertyValue("--desk-ink").trim();
      const strong = styles.getPropertyValue("--desk-ink-strong").trim();
      const thresholds = d3.range(-0.7, 0.71, 0.1).map((v) => +v.toFixed(2));
      const contours = d3.contours().size([gw, gh]).thresholds(thresholds)(Array.from(values));
      const path = d3.geoPath(d3.geoIdentity().scale(Math.max(w / (gw - 1), h / (gh - 1)))).context(ctx);
      for (const c of contours) {
        ctx.beginPath();
        path(c);
        ctx.strokeStyle = Math.abs(c.value) < 0.001 ? strong : ink;
        ctx.lineWidth = Math.abs(c.value) < 0.001 ? 1.4 : 1;
        ctx.stroke();
      }
    };
    draw();
    window.addEventListener("resize", draw);
    return () => window.removeEventListener("resize", draw);
  }, [matrix, resolvedTheme]);

  return <canvas ref={ref} aria-hidden="true" className="pointer-events-none fixed inset-0 -z-0" />;
}
