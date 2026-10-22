import type { Metadata } from "next";

import { AskChat } from "@/components/pages/ask-chat";
import { getAskSuggestions, getVoiceModel, isPreview } from "@/lib/api/client";

export const metadata: Metadata = { title: "Ask" };

export default async function AskPage(props: PageProps<"/ask">) {
  const preview = isPreview();
  const [suggestions, voiceModel, query] = await Promise.all([getAskSuggestions(), getVoiceModel(), props.searchParams]);
  const q = typeof query.q === "string" && query.q.trim().length >= 3 ? query.q.trim().slice(0, 500) : null;
  return <AskChat preview={preview} suggestions={suggestions.state === "ok" ? suggestions.data : []} voiceModel={voiceModel} initialQuestion={q} />;
}
