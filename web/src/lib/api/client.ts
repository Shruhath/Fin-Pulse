import "server-only";

import * as preview from "@/lib/preview";
import type {
  CompanyDetail,
  CorpusStatus,
  DocumentDetail,
  EntityRow,
  EvalReport,
  EventRecord,
  FilingItem,
  Overview,
  SearchIndex,
  Window,
} from "./types";

/**
 * Server-side API access, called from server components.
 *
 * PREVIEW mode (FINPULSE_PREVIEW=1) serves deterministic synthetic data so the
 * interface can be built before the pipeline exists. It is off by default, and
 * every screen shows a persistent "synthetic preview" banner while it is on.
 */

export type ApiResult<T> =
  | { state: "ok"; data: T; preview: boolean }
  | { state: "offline"; message: string }
  | { state: "missing" };

export const API_URL = process.env.FINPULSE_API_URL ?? "http://127.0.0.1:8000";

export const isPreview = () => process.env.FINPULSE_PREVIEW === "1";

async function get<T>(path: string): Promise<ApiResult<T>> {
  try {
    const res = await fetch(`${API_URL}${path}`, { cache: "no-store" });
    if (res.status === 404) return { state: "missing" };
    if (!res.ok) return { state: "offline", message: `The API answered ${res.status} for ${path}.` };
    return { state: "ok", data: (await res.json()) as T, preview: false };
  } catch {
    return { state: "offline", message: `The FinPulse API at ${API_URL} is not reachable.` };
  }
}

function local<T>(data: T | null): ApiResult<T> {
  return data === null ? { state: "missing" } : { state: "ok", data, preview: true };
}

export function parseWindow(value: string | string[] | undefined): Window {
  return value === "7d" || value === "90d" ? value : "30d";
}

export const getOverview = (w: Window) =>
  isPreview() ? Promise.resolve(local<Overview>(preview.previewOverview(w))) : get<Overview>(`/api/overview?window=${w}`);

export const getStatus = () =>
  isPreview()
    ? Promise.resolve(local<CorpusStatus>(preview.previewOverview("30d").corpus))
    : get<CorpusStatus>("/api/status");

export const getCompanies = (w: Window) =>
  isPreview() ? Promise.resolve(local<EntityRow[]>(preview.previewCompanies(w))) : get<EntityRow[]>(`/api/entities?window=${w}`);

export const getCompany = (id: string, w: Window) =>
  isPreview()
    ? Promise.resolve(local<CompanyDetail>(preview.previewCompany(id, w)))
    : get<CompanyDetail>(`/api/entities/${encodeURIComponent(id)}?window=${w}`);

export const getFilings = () =>
  isPreview() ? Promise.resolve(local<FilingItem[]>(preview.previewFilings())) : get<FilingItem[]>("/api/documents");

export const getDocument = (id: string) =>
  isPreview()
    ? Promise.resolve(local<DocumentDetail>(preview.previewDocument(id)))
    : get<DocumentDetail>(`/api/documents/${encodeURIComponent(id)}`);

export const getEvents = (w: Window) =>
  isPreview() ? Promise.resolve(local<EventRecord[]>(preview.previewEvents(w))) : get<EventRecord[]>(`/api/events?window=${w}`);

export const getEval = () =>
  isPreview() ? Promise.resolve(local<EvalReport>(preview.previewEval())) : get<EvalReport>("/api/eval");

export const getSearchIndex = () =>
  isPreview() ? Promise.resolve(local<SearchIndex>(preview.previewSearchIndex())) : get<SearchIndex>("/api/search/index");

export const getWallpaper = () =>
  isPreview() ? Promise.resolve(local<number[][]>(preview.previewWallpaper())) : get<number[][]>("/api/wallpaper");
