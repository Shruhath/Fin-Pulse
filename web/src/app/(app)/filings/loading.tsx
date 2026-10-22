import { HeaderSkeleton, RowsSkeleton, ToolbarSkeleton } from "@/components/app/skeletons";

export default function Loading() {
  return (
    <div aria-busy="true" aria-label="Loading">
      <HeaderSkeleton />
      <ToolbarSkeleton />
      <RowsSkeleton rows={8} />
    </div>
  );
}
