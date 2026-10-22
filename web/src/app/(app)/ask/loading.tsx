import { ChatSkeleton } from "@/components/app/skeletons";

export default function Loading() {
  return (
    <div aria-busy="true" aria-label="Loading">
      <ChatSkeleton />
    </div>
  );
}
