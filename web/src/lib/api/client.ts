import "server-only";

import { previewOverview } from "@/lib/preview/overview";
import type { Overview, Window } from "./types";

/**
 * Server-side API access. Pages call these from server components.
 *
 * PREVIEW mode (FINPULSE_PREVIEW=1) serves deterministic synthetic data so the
 * interface can be built before the pipeline exists. It is off by default, and
 * every screen shows a persistent "synthetic preview" banner while it is on.
 * Nothing in preview mode is a model result.
 */

export type ApiResult<T> =
  | { state: "ok"; data: T; preview: boolean }
  | { state: "offline"; message: string };

const API_URL = process.env.FINPULSE_API_URL ?? "http://127.0.0.1:8000";

export const isPreview = () => process.env.FINPULSE_PREVIEW === "1";

async function get<T>(path: string): Promise<ApiResult<T>> {
  try {
    const res = await fetch(`${API_URL}${path}`, { cache: "no-store" });
    if (!res.ok) {
      return { state: "offline", message: `The API answered ${res.status} for ${path}.` };
    }
    return { state: "ok", data: (await res.json()) as T, preview: false };
  } catch {
    return { state: "offline", message: `The FinPulse API at ${API_URL} is not reachable.` };
  }
}

export function parseWindow(value: string | string[] | undefined): Window {
  return value === "7d" || value === "90d" ? value : "30d";
}

export async function getOverview(window: Window): Promise<ApiResult<Overview>> {
  if (isPreview()) return { state: "ok", data: previewOverview(window), preview: true };
  return get<Overview>(`/api/overview?window=${window}`);
}
