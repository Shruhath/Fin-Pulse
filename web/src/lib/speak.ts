import { useSyncExternalStore } from "react";

import type { AskAnswer } from "@/lib/api/types";

/**
 * Reading an answer aloud with the operating system's own voice. Only voices that run on this machine are
 * used: some browsers also list voices that stream from a server, and those would send the answer's text away.
 */
const localEnglishVoice = (): SpeechSynthesisVoice | null =>
  typeof speechSynthesis === "undefined"
    ? null
    : (speechSynthesis.getVoices().find((v) => v.localService && v.lang.toLowerCase().startsWith("en")) ?? null);

function subscribe(notify: () => void) {
  if (typeof speechSynthesis === "undefined") return () => {};
  speechSynthesis.addEventListener("voiceschanged", notify);
  return () => speechSynthesis.removeEventListener("voiceschanged", notify);
}

export const useCanSpeak = () =>
  useSyncExternalStore(subscribe, () => localEnglishVoice() !== null, () => false);

export function stopSpeaking() {
  if (typeof speechSynthesis !== "undefined") speechSynthesis.cancel();
}

export function speak(text: string, onEnd: () => void) {
  const voice = localEnglishVoice();
  if (!voice) return onEnd();
  stopSpeaking();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.voice = voice;
  utterance.onend = onEnd;
  utterance.onerror = onEnd;
  speechSynthesis.speak(utterance);
}

/** What is read out: only claims a filing confirmed, never a draft, or else why there is no answer. */
export function spokenAnswer(answer: AskAnswer): string {
  if (answer.abstained) return answer.reason ?? "There is no answer in the filings.";
  const confirmed = answer.claims.filter((c) => c.verification === "entailed").map((c) => c.text);
  return confirmed.length > 0 ? `Confirmed by the filings. ${confirmed.join(" ")}` : "No claim could be confirmed by the filings.";
}
