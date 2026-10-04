import type { Metadata } from "next";

import { AnalyzeWorkspace } from "@/components/workspaces/analyze";
import { getDocument, isPreview } from "@/lib/api/client";

export const metadata: Metadata = { title: "Analyze" };

export default async function AnalyzePage() {
  const preview = isPreview();
  // preview mode bundles one sample filing; a live API analyses real input
  const sample = preview ? await getDocument("bse-infy-guidance") : null;
  return <AnalyzeWorkspace preview={preview} sample={sample?.state === "ok" ? sample.data : null} />;
}
