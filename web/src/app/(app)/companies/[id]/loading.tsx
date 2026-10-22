import { HeaderSkeleton, PanelSkeleton } from "@/components/app/skeletons";

export default function Loading() {
  return (
    <div aria-busy="true" aria-label="Loading">
      <HeaderSkeleton />
      <PanelSkeleton height={84} />
      <div className="mt-8 space-y-6">
        <PanelSkeleton height={300} />
        <PanelSkeleton height={180} />
      </div>
    </div>
  );
}
