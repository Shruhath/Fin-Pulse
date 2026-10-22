import { HeaderSkeleton, PanelSkeleton, RowsSkeleton } from "@/components/app/skeletons";

export default function Loading() {
  return (
    <div aria-busy="true" aria-label="Loading">
      <HeaderSkeleton />
      <div className="mb-5 h-11 border-b border-line" />
      <PanelSkeleton height={44} />
      <RowsSkeleton rows={8} className="mt-3" />
    </div>
  );
}
