import { HeaderSkeleton, PanelSkeleton, RowsSkeleton } from "@/components/app/skeletons";

export default function Loading() {
  return (
    <div aria-busy="true" aria-label="Loading">
      <HeaderSkeleton />
      <PanelSkeleton height={64} />
      <div className="mt-12 grid gap-12 lg:grid-cols-[minmax(0,1fr)_340px]">
        <RowsSkeleton rows={6} />
        <div className="space-y-6">
          <PanelSkeleton height={230} />
          <PanelSkeleton height={230} />
        </div>
      </div>
    </div>
  );
}
