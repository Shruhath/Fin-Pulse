import type { Metadata } from "next";

import { AskWorkspace } from "@/components/workspaces/ask";
import { getAskSuggestions, getVoiceModel, isPreview } from "@/lib/api/client";

export const metadata: Metadata = { title: "Ask" };

export default async function AskPage() {
  const preview = isPreview();
  const [suggestions, voiceModel] = await Promise.all([getAskSuggestions(), getVoiceModel()]);
  return (
    <AskWorkspace preview={preview} suggestions={suggestions.state === "ok" ? suggestions.data : []} voiceModel={voiceModel} />
  );
}
