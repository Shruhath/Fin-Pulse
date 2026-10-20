import type { Metadata } from "next";

import { AskWorkspace } from "@/components/workspaces/ask";
import { getAskSuggestions, isPreview } from "@/lib/api/client";

export const metadata: Metadata = { title: "Ask" };

export default async function AskPage() {
  const preview = isPreview();
  const suggestions = await getAskSuggestions();
  return <AskWorkspace preview={preview} suggestions={suggestions.state === "ok" ? suggestions.data : []} />;
}
