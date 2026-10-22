import clsx from "clsx";

/** Placeholders shaped like the page that is about to appear, so moving between pages never blanks the screen. */

const bone = "skeleton";

export function HeaderSkeleton({ desc = true }: { desc?: boolean }) {
  return (
    <div className="mb-7">
      <div className={clsx(bone, "h-10 w-56")} />
      {desc && <div className={clsx(bone, "mt-3 h-5 w-full max-w-md")} />}
    </div>
  );
}

export function RowsSkeleton({ rows = 6, className }: { rows?: number; className?: string }) {
  return (
    <div className={clsx("divide-y divide-line overflow-hidden rounded-2xl border border-line bg-surface", className)}>
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="flex gap-4 px-4 py-4" style={{ opacity: 1 - i * 0.1 }}>
          <div className={clsx(bone, "mt-0.5 h-5 w-11 shrink-0")} />
          <div className="min-w-0 flex-1 space-y-2">
            <div className={clsx(bone, "h-5 w-[78%]")} />
            <div className={clsx(bone, "h-4 w-[40%]")} />
          </div>
        </div>
      ))}
    </div>
  );
}

export function ToolbarSkeleton() {
  return (
    <div className="mb-5 flex flex-wrap gap-3">
      <div className={clsx(bone, "h-11 w-full max-w-sm rounded-xl")} />
      <div className={clsx(bone, "h-10 w-64 rounded-full")} />
    </div>
  );
}

export function PanelSkeleton({ height = 260 }: { height?: number }) {
  return <div className={clsx(bone, "w-full rounded-2xl")} style={{ height }} />;
}

export function ReaderSkeleton() {
  return (
    <div className="grid gap-10 xl:grid-cols-[minmax(0,1fr)_410px]">
      <div>
        <div className={clsx(bone, "h-5 w-64")} />
        <div className={clsx(bone, "mt-4 h-9 w-[80%]")} />
        <div className="mt-10 space-y-3">
          {Array.from({ length: 9 }, (_, i) => (
            <div key={i} className={clsx(bone, "h-5")} style={{ width: `${96 - ((i * 13) % 28)}%` }} />
          ))}
        </div>
      </div>
      <div className="hidden xl:block">
        <PanelSkeleton height={420} />
      </div>
    </div>
  );
}

export function ChatSkeleton() {
  return (
    <div className="mx-auto max-w-3xl">
      <HeaderSkeleton />
      <div className={clsx(bone, "h-[60px] w-full rounded-3xl")} />
      <div className="mt-10 space-y-3">
        <div className={clsx(bone, "h-6 w-40")} />
        {[0, 1, 2].map((i) => (
          <div key={i} className={clsx(bone, "h-11 rounded-2xl")} style={{ width: `${70 - i * 10}%` }} />
        ))}
      </div>
    </div>
  );
}
