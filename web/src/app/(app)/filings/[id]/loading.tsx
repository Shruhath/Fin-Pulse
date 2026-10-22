import { ReaderSkeleton } from "@/components/app/skeletons";

export default function Loading() {
  return (
    <div aria-busy="true" aria-label="Loading">
      <ReaderSkeleton />
    </div>
  );
}
