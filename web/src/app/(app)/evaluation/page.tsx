import type { Metadata } from "next";

import { EvaluationView } from "@/components/pages/evaluation-view";
import { OfflineState } from "@/components/ui/states";
import { getEval, isPreview } from "@/lib/api/client";

export const metadata: Metadata = { title: "Evaluation" };

export default async function EvaluationPage() {
  const res = await getEval();
  if (res.state === "offline") return <OfflineState message={res.message} />;
  const report = res.state === "ok" ? res.data : { generatedAt: null, rows: [], confusion: null, reliability: null, agreement: [] };
  return <EvaluationView report={report} preview={isPreview()} />;
}
