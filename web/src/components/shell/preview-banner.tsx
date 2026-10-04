import { FlaskConical } from "lucide-react";

/** Persistent, unmissable notice whenever synthetic preview data is on screen. */
export function PreviewBanner() {
  return (
    <div role="status" className="flex items-center gap-2 border-b border-warn/30 bg-warn-weak px-4 py-1.5 text-xs text-warn sm:px-6">
      <FlaskConical className="size-3.5 shrink-0" strokeWidth={2} aria-hidden="true" />
      <p>
        <strong className="font-semibold">Synthetic preview.</strong> Every number, event and headline on this
        screen is invented for interface development. None of it is model output.
      </p>
    </div>
  );
}
