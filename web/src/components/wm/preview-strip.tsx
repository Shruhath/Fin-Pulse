import { FlaskConical } from "lucide-react";

/** Persistent notice whenever synthetic preview data is on screen. */
export function PreviewStrip() {
  return (
    <div role="status" className="relative z-10 flex shrink-0 items-center gap-2 border-b border-warn/40 bg-[#2a1d06] px-3 py-1 font-mono text-2xs text-[#ffc76b]">
      <FlaskConical className="size-3 shrink-0" aria-hidden="true" />
      <p className="truncate">
        <strong className="font-semibold">synthetic preview</strong>
        <span className="opacity-80"> · every figure, event, headline and verdict here is invented for interface work. none of it is model output.</span>
      </p>
    </div>
  );
}
