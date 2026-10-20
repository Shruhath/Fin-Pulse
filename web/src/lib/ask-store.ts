import type { AskJob } from "@/lib/api/types";

/**
 * The conversation on the ask screen, kept in this browser tab (sessionStorage) so that opening a filing from
 * an answer and coming back finds it again. It never leaves the browser and is gone when the tab closes.
 */
export interface Turn {
  id: string;
  question: string;
  jobId: string | null;
  job: AskJob | null;
  error: string | null;
}

const KEY = "finpulse.ask.v1";
const KEEP = 20;
const EMPTY: Turn[] = [];

let turns: Turn[] | null = null;
const listeners = new Set<() => void>();

function load(): Turn[] {
  try {
    const parsed: unknown = JSON.parse(sessionStorage.getItem(KEY) ?? "[]");
    return Array.isArray(parsed) ? (parsed as Turn[]) : [];
  } catch {
    return []; // private window or cleared storage
  }
}

export const getTurns = (): Turn[] => (turns ??= load());

/** What the server renders, so the first client render matches it. */
export const getServerTurns = (): Turn[] => EMPTY;

export function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function updateTurns(change: (all: Turn[]) => Turn[]) {
  turns = change(getTurns()).slice(-KEEP);
  try {
    sessionStorage.setItem(KEY, JSON.stringify(turns));
  } catch {
    /* storage unavailable: the conversation just is not kept */
  }
  listeners.forEach((l) => l());
}
