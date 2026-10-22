import { HeaderSkeleton, PanelSkeleton, RowsSkeleton } from "@/components/app/skeletons";

export default function Loading() {
  return (
    <div aria-busy="true" aria-label="Loading">
      <HeaderSkeleton />
      <PanelSkeleton height={44} />
      <div className="mt-8">
        <PanelSkeleton height={230} />
      </div>
      <RowsSkeleton rows={5} className="mt-8" />
    </div>
  );
}
