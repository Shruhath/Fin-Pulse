"use client";

import { useLayoutEffect, useRef, useState } from "react";

/**
 * Measures the active child of a control so an indicator can slide to it.
 * The child is whichever element carries data-active="true" or data-state="active".
 */
export function useSlider<T extends HTMLElement>(deps: unknown[]) {
  const ref = useRef<T>(null);
  const [box, setBox] = useState<{ x: number; y: number; w: number; h: number } | null>(null);

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const measure = () => {
      const active = el.querySelector<HTMLElement>('[data-active="true"], [data-state="active"]');
      setBox(active ? { x: active.offsetLeft, y: active.offsetTop, w: active.offsetWidth, h: active.offsetHeight } : null);
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return [ref, box] as const;
}
