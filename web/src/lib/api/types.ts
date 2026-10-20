/**
 * Response shapes served by the FinPulse API (server/src/finpulse/api).
 *
 * Derived from the generated OpenAPI types (`bun run gen:api`), so the Pydantic models are the single
 * source of truth: a field the API can leave null is nullable here too, and the compiler lists every
 * place that has to cope with it. Only the closed vocabularies the UI switches on are narrowed.
 */

import type { components } from "./schema";

type S = components["schemas"];

export type SentimentLabel = NonNullable<S["EntityRow"]["sentiment"]>;

export type Verification = S["Claim"]["verification"];

export type SourceKind = S["FilingItem"]["source"];

/** The windows the UI offers; the API also accepts 365d and all. */
export type Window = Extract<S["Overview"]["window"], "7d" | "30d" | "90d">;

/** EDT's 11 corporate types plus the five India-specific types (server/src/finpulse/events/taxonomy.py). */
export type EventType =
  | "Acquisition"
  | "Clinical Trial"
  | "Guidance Change"
  | "New Contract"
  | "Stock Repurchase"
  | "Stock Split"
  | "Reverse Split"
  | "Regular Dividend"
  | "Special Dividend"
  | "Dividend Cut"
  | "Dividend Increase"
  | "SEBI Penalty"
  | "RBI Action"
  | "NCLT Admission"
  | "Pledge Invocation"
  | "Auditor Resignation";

export type EventGroup = "Corporate action" | "Dividend" | "Regulatory" | "Governance" | "Insolvency";

/** The taxonomy is closed on the server, so the two free-text fields in the schema are narrowed here. */
type Typed<T> = Omit<T, "type" | "group"> & { type: EventType; group: EventGroup };

export type CorpusStatus = S["CorpusStatus"];
export type SourceCount = S["SourceCount"];
export type MarketPoint = S["MarketPoint"];
export type SeriesPoint = S["SeriesPoint"];
export type EntityRow = S["EntityRow"];
export type EventMarker = Typed<S["EventMarker"]>;
export type FilingEntity = S["FilingEntity"];
export type FilingItem = S["FilingItem"];
export type Overview = Omit<S["Overview"], "events" | "window"> & { events: EventMarker[]; window: Window };

export const EVENT_GROUP: Record<EventType, EventGroup> = {
  Acquisition: "Corporate action",
  "Clinical Trial": "Corporate action",
  "Guidance Change": "Corporate action",
  "New Contract": "Corporate action",
  "Stock Repurchase": "Corporate action",
  "Stock Split": "Corporate action",
  "Reverse Split": "Corporate action",
  "Regular Dividend": "Dividend",
  "Special Dividend": "Dividend",
  "Dividend Cut": "Dividend",
  "Dividend Increase": "Dividend",
  "SEBI Penalty": "Regulatory",
  "RBI Action": "Regulatory",
  "NCLT Admission": "Insolvency",
  "Pledge Invocation": "Governance",
  "Auditor Resignation": "Governance",
};

/* ---------- documents, events, summaries ---------- */

/** Character offsets into DocumentDetail.text; the UI renders by slicing. */
export type EntitySpan = S["EntitySpan"];
export type EventRecord = Typed<S["EventRecord"]>;
export type Evidence = S["Evidence"];
export type Claim = S["Claim"];
export type Summary = S["Summary"];
export type DocumentDetail = Omit<S["DocumentDetail"], "events"> & { events: EventRecord[] };
export type Mention = S["Mention"];
export type CompanyDetail = Omit<S["CompanyDetail"], "events"> & { events: EventRecord[] };

/* ---------- evaluation ---------- */

export type MetricRow = S["MetricRow"];
export type Confusion = S["Confusion"];
export type ReliabilityBin = S["ReliabilityBin"];
export type EvalReport = S["EvalReport"];

/* ---------- analyze jobs ---------- */

export type StageKey = S["JobStage"]["key"];
export type JobStage = S["JobStage"];
export type Job = S["Job"];

/* ---------- questions ---------- */

export type AskStage = S["AskStage"];
export type AskPassage = S["AskPassage"];
export type AskAnswer = S["AskAnswer"];
export type AskJob = S["AskJob"];

/* ---------- launcher index ---------- */

export type SearchIndex = S["SearchIndex"];
