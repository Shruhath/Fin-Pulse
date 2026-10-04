import { OfflineState } from "@/components/ui/states";
import { OverviewWorkspace } from "@/components/workspaces/overview";
import { getOverview, parseWindow } from "@/lib/api/client";
import { WINDOW_LABEL } from "@/lib/format";

export default async function OverviewPage(props: PageProps<"/">) {
  const w = parseWindow((await props.searchParams).w);
  const res = await getOverview(w);
  if (res.state !== "ok") return <OfflineState message={res.state === "offline" ? res.message : "The overview is empty."} />;
  return <OverviewWorkspace data={res.data} windowLabel={WINDOW_LABEL[w]} />;
}
