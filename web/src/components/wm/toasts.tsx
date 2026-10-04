"use client";

import { useRef } from "react";
import { gsap } from "gsap";
import { useGSAP } from "@gsap/react";
import { X } from "lucide-react";
import clsx from "clsx";

import { useWM, type Toast } from "./wm";

const TONE: Record<NonNullable<Toast["tone"]>, string> = {
  info: "border-l-info",
  ok: "border-l-pos",
  warn: "border-l-warn",
  error: "border-l-neg",
};

/** Notification daemon: stacked, top-right, under the bar. */
export function Toasts() {
  const { toasts, dismiss } = useWM();
  return (
    <div aria-live="polite" className="pointer-events-none fixed top-[calc(var(--bar-h)+12px)] right-3 z-50 flex w-[min(340px,calc(100vw-24px))] flex-col gap-2">
      {toasts.map((t) => (
        <ToastCard key={t.id} toast={t} onClose={() => dismiss(t.id)} />
      ))}
    </div>
  );
}

function ToastCard({ toast, onClose }: { toast: Toast; onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  useGSAP(
    () => {
      const mm = gsap.matchMedia();
      mm.add("(prefers-reduced-motion: no-preference)", () => {
        gsap.from(ref.current, { x: 36, opacity: 0, duration: 0.4, ease: "expo.out" });
      });
      return () => mm.revert();
    },
    { scope: ref },
  );
  return (
    <div
      ref={ref}
      role="status"
      className={clsx("pointer-events-auto border border-l-2 border-line bg-surface p-2.5 shadow-pop", TONE[toast.tone ?? "info"])}
    >
      <div className="flex items-center gap-2 font-mono text-2xs text-ink-3">
        <span>{toast.app}</span>
        <button type="button" onClick={onClose} aria-label="Dismiss notification" className="ml-auto text-ink-3 hover:text-ink">
          <X className="size-3" />
        </button>
      </div>
      <p className="mt-1 text-sm font-semibold text-ink">{toast.title}</p>
      {toast.body && <p className="mt-0.5 text-xs text-ink-2">{toast.body}</p>}
    </div>
  );
}
