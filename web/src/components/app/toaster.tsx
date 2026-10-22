"use client";

import { AlertTriangle, CheckCircle2, Info, X, XCircle } from "lucide-react";
import clsx from "clsx";

import { useApp } from "./app-context";

const TONE = {
  info: { icon: Info, ink: "text-brand-ink" },
  ok: { icon: CheckCircle2, ink: "text-pos" },
  warn: { icon: AlertTriangle, ink: "text-warn" },
  error: { icon: XCircle, ink: "text-neg" },
} as const;

export function Toaster() {
  const { toasts, dismiss } = useApp();
  return (
    <div aria-live="polite" className="pointer-events-none fixed right-4 bottom-20 z-50 flex w-[min(360px,calc(100vw-32px))] flex-col gap-2 lg:bottom-6 lg:right-6">
      {toasts.map((t) => {
        const { icon: Icon, ink } = TONE[t.tone ?? "info"];
        return (
          <div key={t.id} role="status" className="fade-up pointer-events-auto flex gap-3 rounded-2xl border border-line bg-surface p-3.5 shadow-pop">
            <Icon className={clsx("mt-0.5 size-5 shrink-0", ink)} aria-hidden="true" />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold text-ink">{t.title}</p>
              {t.body && <p className="mt-0.5 text-sm text-ink-2">{t.body}</p>}
            </div>
            <button type="button" onClick={() => dismiss(t.id)} aria-label="Dismiss" className="-mt-1 -mr-1 inline-flex size-8 items-center justify-center rounded-full text-ink-3 hover:bg-surface-2">
              <X className="size-4" aria-hidden="true" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
