/**
 * Response shapes served by the FinPulse API (server/src/finpulse/api).
 *
 * Hand-written until the FastAPI service exists; once it does, these are
 * replaced by types generated from /openapi.json (`bun run gen:api`), and the
 * Pydantic models become the single source of truth.
 */

export type SentimentLabel = "positive" | "negative" | "neutral";

export type Verification = "entailed" | "contradicted" | "unverified";

export type SourceKind = "BSE" | "NSE" | "SEBI" | "RBI" | "NCLT" | "NEWS";

export type Window = "7d" | "30d" | "90d";

/** EDT's 11 corporate types plus the five India-specific types. */
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

export interface CorpusStatus {
  documents: number;
  entities: number;
  events: number;
  /** ISO timestamp of the most recent completed ingest run */
  lastIngestAt: string | null;
}

export interface SourceCount {
  kind: SourceKind;
  documents: number;
}

/** One day of the market aggregate: mean and spread of entity scores. */
export interface MarketPoint {
  t: string;
  mean: number;
  std: number;
  /** number of scored mentions that day */
  n: number;
}

export interface SeriesPoint {
  t: string;
  /** mean entity score that day, -1..1 */
  v: number;
}

export interface EntityRow {
  id: string;
  name: string;
  ticker: string;
  sector: string;
  /** aggregate score over the window, -1..1 */
  score: number;
  /** change vs the previous window */
  delta: number;
  sentiment: SentimentLabel;
  mentions: number;
  /** mean calibrated confidence, 0..1 */
  confidence: number;
  series: SeriesPoint[];
}

export interface EventMarker {
  id: string;
  t: string;
  type: EventType;
  group: EventGroup;
  entityId: string;
  entityName: string;
  headline: string;
  source: SourceKind;
  documentId: string;
}

export interface FilingEntity {
  id: string;
  name: string;
  sentiment: SentimentLabel;
}

export interface FilingItem {
  id: string;
  title: string;
  source: SourceKind;
  publishedAt: string;
  entities: FilingEntity[];
  status: "ingested" | "parsed" | "analysed" | "failed";
}

export interface Overview {
  window: Window;
  corpus: CorpusStatus;
  sources: SourceCount[];
  market: MarketPoint[];
  events: EventMarker[];
  entities: EntityRow[];
  filings: FilingItem[];
}

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
export interface EntitySpan {
  start: number;
  end: number;
  entityId: string;
  surface: string;
  sentiment: SentimentLabel;
  /** calibrated confidence of the entity-sentiment head, 0..1 */
  confidence: number;
}

export interface EventRecord extends EventMarker {
  sentiment: SentimentLabel;
  confidence: number;
  /** offsets of the trigger sentence in the source document's text */
  trigger: { start: number; end: number } | null;
  arguments: Record<string, string>;
  extractor: "llm" | "rules";
}

export interface Evidence {
  documentId: string;
  documentTitle: string;
  source: SourceKind;
  text: string;
}

export interface Claim {
  id: string;
  text: string;
  verification: Verification;
  /** NLI entailment and contradiction probabilities, 0..1 */
  entail: number;
  contradict: number;
  evidence: Evidence | null;
}

export interface Summary {
  id: string;
  scope: "document" | "entity";
  model: string;
  generatedAt: string;
  claims: Claim[];
}

export interface DocumentDetail extends FilingItem {
  url: string;
  words: number;
  ocr: boolean;
  text: string;
  spans: EntitySpan[];
  events: EventRecord[];
  summary: Summary | null;
}

export interface Mention {
  documentId: string;
  documentTitle: string;
  source: SourceKind;
  publishedAt: string;
  sentence: string;
  /** offsets of the mention inside `sentence` */
  start: number;
  end: number;
  sentiment: SentimentLabel;
  confidence: number;
}

export interface CompanyDetail {
  entity: EntityRow;
  aliases: string[];
  events: EventRecord[];
  mentions: Mention[];
  summary: Summary | null;
}

/* ---------- evaluation ---------- */

export interface MetricRow {
  task: "ner" | "sentiment" | "events" | "summaries";
  model: string;
  baseline: boolean;
  dataset: string;
  /** India gold slice vs public benchmark: the transfer gap is RQ4 */
  indian: boolean;
  metrics: Record<string, number>;
}

export interface Confusion {
  model: string;
  dataset: string;
  labels: SentimentLabel[];
  /** rows = gold, columns = predicted */
  matrix: number[][];
}

export interface ReliabilityBin {
  confidence: number;
  accuracy: number;
  n: number;
}

export interface EvalReport {
  generatedAt: string | null;
  rows: MetricRow[];
  confusion: Confusion | null;
  reliability: { before: ReliabilityBin[]; after: ReliabilityBin[]; eceBefore: number; eceAfter: number } | null;
  agreement: { task: string; kappa: number; items: number }[];
}

/* ---------- analyze jobs ---------- */

export type StageKey = "ingest" | "parse" | "entities" | "sentiment" | "events" | "summary" | "verify";

export interface JobStage {
  key: StageKey;
  status: "pending" | "running" | "done" | "failed" | "skipped";
  ms: number | null;
  note: string | null;
}

export interface Job {
  id: string;
  status: "queued" | "running" | "done" | "failed";
  stages: JobStage[];
  documentId: string | null;
}

/* ---------- launcher index ---------- */

export interface SearchIndex {
  companies: { id: string; name: string; ticker: string }[];
  filings: { id: string; title: string; source: SourceKind }[];
}
