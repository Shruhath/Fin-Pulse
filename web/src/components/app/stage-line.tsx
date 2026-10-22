"use client";

import { Check, X } from "lucide-react";
import clsx from "clsx";

export interface Stage {
  key: string;
  label: string;
  how?: string;
  status: "pending" | "running" | "done" | "failed" | "skipped";
  ms?: number | null;
  note?: string | null;
}

const time = (ms: number) => (ms >= 1000 ? `${(ms / 1000).toFixed(1)} s` : `${ms} ms`);

/**
 * The pipeline as one line with a station for each stage. A finished stage fills the line behind
 * it; the running stage sends a light along the next stretch. Vertical on a phone, horizontal above.
 */
export function StageLine({ stages, showHow = false }: { stages: Stage[]; showHow?: boolean }) {
  return (
    <ol className="flex flex-col sm:flex-row" aria-label="Pipeline stages">
      {stages.map((s, i) => {
        const last = i === stages.length - 1;
        return (
          <li key={s.key} className="relative flex flex-1 gap-3 pb-5 last:pb-0 sm:flex-col sm:gap-0 sm:pb-0">
            <div className="flex flex-col items-center sm:w-full sm:flex-row">
              <Station status={s.status} />
              {!last && (
                <span className="relative my-1 w-0.5 flex-1 overflow-hidden rounded-full bg-surface-3 sm:my-0 sm:ml-0 sm:h-0.5 sm:w-auto" aria-hidden="true">
                  <span className={clsx("absolute inset-0 origin-left rounded-full bg-pos transition-transform duration-500 ease-(--ease-out)", s.status === "done" ? "scale-100" : "scale-0")} />
                  {s.status === "running" && (
                    <span className="absolute inset-y-0 left-0 w-1/3 rounded-full bg-brand" style={{ animation: "sweep 1.2s var(--ease-out) infinite" }} />
                  )}
                </span>
              )}
            </div>
            <div className="min-w-0 pr-2 sm:mt-3">
              <p className={clsx("text-sm leading-5 font-semibold", s.status === "pending" || s.status === "skipped" ? "text-ink-3" : "text-ink")}>{s.label}</p>
              {s.ms != null && s.ms >= 0 && s.status === "done" && <p className="num text-xs text-ink-3">{time(s.ms)}</p>}
              {(showHow || s.status === "failed") && (s.note || s.how) && (
                <p className={clsx("mt-0.5 text-xs leading-4", s.status === "failed" ? "text-neg" : "text-ink-3")}>{s.note ?? s.how}</p>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

function Station({ status }: { status: Stage["status"] }) {
  return (
    <span
      role="img"
      aria-label={status}
      className={clsx(
        "relative z-[1] inline-flex size-7 shrink-0 items-center justify-center rounded-full border-2 transition-colors duration-300",
        status === "done" && "border-pos bg-pos text-white",
        status === "failed" && "border-neg bg-neg text-white",
        status === "running" && "border-brand bg-surface",
        (status === "pending" || status === "skipped") && "border-line-strong bg-surface",
      )}
      style={status === "running" ? { animation: "pulse-ring 1.3s ease-out infinite" } : undefined}
    >
      {status === "done" && <Check className="size-4" strokeWidth={3} aria-hidden="true" />}
      {status === "failed" && <X className="size-4" strokeWidth={3} aria-hidden="true" />}
      {status === "running" && <span className="size-2.5 rounded-full bg-brand" />}
    </span>
  );
}
