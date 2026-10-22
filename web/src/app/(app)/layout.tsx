import { AppShell } from "@/components/app/shell";
import { getSearchIndex, getStatus, isPreview } from "@/lib/api/client";

// Every page behind this layout reads the live API, so none of them may be built ahead of time.
export const dynamic = "force-dynamic";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const [status, index] = await Promise.all([getStatus(), getSearchIndex()]);
  return (
    <AppShell corpus={status.state === "ok" ? status.data : null} index={index.state === "ok" ? index.data : null} preview={isPreview()}>
      {children}
    </AppShell>
  );
}
