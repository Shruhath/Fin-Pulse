import { HeaderSkeleton, PanelSkeleton } from "@/components/app/skeletons";

export default function Loading() {
  return (
    <div aria-busy="true" aria-label="Loading">
      <HeaderSkeleton />
      <div className="max-w-3xl">
        <PanelSkeleton height={460} />
      </div>
    </div>
  );
}
