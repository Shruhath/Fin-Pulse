/**
 * SYNTHETIC PREVIEW API, not model output. Mirrors the FastAPI responses so
 * every workspace can be built before the pipeline exists. Only served when
 * FINPULSE_PREVIEW=1, and every screen is bannered while it is.
 */

import type {
  Claim,
  CompanyDetail,
  DocumentDetail,
  EntityRow,
  EntitySpan,
  EvalReport,
  EventRecord,
  FilingItem,
  MarketPoint,
  Mention,
  Overview,
  SearchIndex,
  SentimentLabel,
  Summary,
  Window,
} from "@/lib/api/types";
import { EVENT_GROUP } from "@/lib/api/types";
import { AS_OF, COMPANIES, DAY, DOCS, EXTRA_EVENTS, type DocSeed } from "./corpus";

const HISTORY = 180;
const WINDOW_DAYS: Record<Window, number> = { "7d": 7, "30d": 30, "90d": 90 };

function mulberry32(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const isoDay = (offset: number) => new Date(AS_OF - offset * DAY).toISOString().slice(0, 10);
const isoAt = (day: number, hour: number) => new Date(AS_OF - day * DAY - hour * 3_600_000).toISOString();
const clamp = (v: number) => Math.max(-1, Math.min(1, v));
const label = (v: number): SentimentLabel => (v > 0.12 ? "positive" : v < -0.12 ? "negative" : "neutral");
const NAME = new Map(COMPANIES.map((c) => [c[0], c[1]]));

/* ---------- series ---------- */

type Pt = { t: string; v: number; n: number };
let SERIES: Map<string, Pt[]> | null = null;
function series() {
  if (SERIES) return SERIES;
  SERIES = new Map();
  COMPANIES.forEach(([id, , , , target, vol], i) => {
    const rnd = mulberry32(1000 + i * 97);
    let v = target * 0.4;
    const s: Pt[] = [];
    for (let d = HISTORY - 1; d >= 0; d--) {
      v = clamp(v + 0.18 * (target - v) + (rnd() - 0.5) * vol * 2);
      s.push({ t: isoDay(d), v: +v.toFixed(3), n: rnd() < 0.18 ? 0 : 1 + Math.floor(rnd() * 6) });
    }
    SERIES!.set(id, s);
  });
  return SERIES;
}

function entityRows(window: Window): EntityRow[] {
  const days = WINDOW_DAYS[window];
  return COMPANIES.map(([id, name, ticker, sector], i) => {
    const s = series().get(id)!;
    const cur = s.slice(-days).filter((p) => p.n > 0);
    const prev = s.slice(-2 * days, -days).filter((p) => p.n > 0);
    const avg = (xs: Pt[]) => xs.reduce((a, p) => a + p.v, 0) / Math.max(xs.length, 1);
    const score = +avg(cur).toFixed(2);
    return {
      id,
      name,
      ticker,
      sector,
      score,
      delta: +(score - avg(prev)).toFixed(2),
      sentiment: label(score),
      mentions: cur.reduce((a, p) => a + p.n, 0),
      confidence: +(0.62 + mulberry32(7 + i)() * 0.3).toFixed(2),
      series: s.slice(-days).map(({ t, v }) => ({ t, v })),
    };
  });
}

/* ---------- documents ---------- */

function spansOf(d: DocSeed): EntitySpan[] {
  const out: EntitySpan[] = [];
  // longest surfaces first so "Paytm" never claims part of a longer name
  const seeds = [...d.mentions].sort((a, b) => b[0].length - a[0].length);
  for (const [surface, entityId, sentiment, confidence] of seeds) {
    let from = 0;
    for (;;) {
      const i = d.text.indexOf(surface, from);
      if (i < 0) break;
      const end = i + surface.length;
      if (!out.some((s) => i < s.end && end > s.start)) out.push({ start: i, end, entityId, surface, sentiment, confidence });
      from = end;
    }
  }
  return out.sort((a, b) => a.start - b.start);
}

function eventsOf(d: DocSeed): EventRecord[] {
  return d.events.map(([type, entityId, trigger, args, sentiment, confidence, extractor], i) => {
    const s = d.text.indexOf(trigger);
    return {
      id: `${d.id}-ev${i}`,
      t: isoAt(d.day, d.hour),
      type,
      group: EVENT_GROUP[type],
      entityId,
      entityName: NAME.get(entityId)!,
      headline: trigger.length > 120 ? `${trigger.slice(0, 117)}…` : trigger,
      source: d.source,
      documentId: d.id,
      sentiment,
      confidence,
      trigger: s >= 0 ? { start: s, end: s + trigger.length } : null,
      arguments: args,
      extractor,
    };
  });
}

function summaryOf(d: DocSeed): Summary | null {
  if (d.claims.length === 0) return null;
  const claims: Claim[] = d.claims.map(([text, verification, evidence, entail, contradict], i) => ({
    id: `${d.id}-c${i}`,
    text,
    verification,
    entail,
    contradict,
    evidence: evidence ? { documentId: d.id, documentTitle: d.title, source: d.source, text: evidence } : null,
  }));
  return { id: `${d.id}-sum`, scope: "document", model: "llama3.1:8b-instruct + DeBERTa-v3 NLI", generatedAt: isoAt(d.day, d.hour - 1), claims };
}

function filingOf(d: DocSeed): FilingItem {
  const byEntity = new Map<string, SentimentLabel>();
  for (const [, id, s] of d.mentions) if (!byEntity.has(id)) byEntity.set(id, s);
  return {
    id: d.id,
    title: d.title,
    source: d.source,
    publishedAt: isoAt(d.day, d.hour),
    entities: [...byEntity].map(([id, sentiment]) => ({ id, name: NAME.get(id)!, sentiment })),
    status: d.status,
  };
}

const sentences = (text: string) => {
  const out: { start: number; end: number }[] = [];
  const re = /[^.]+(?:\.(?!\d)|$)/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text))) {
    const lead = m[0].length - m[0].trimStart().length;
    if (m[0].trim()) out.push({ start: m.index + lead, end: m.index + m[0].length });
  }
  return out;
};

/* ---------- public ---------- */

export function previewFilings(): FilingItem[] {
  return DOCS.map(filingOf);
}

export function previewDocument(id: string): DocumentDetail | null {
  const d = DOCS.find((x) => x.id === id);
  if (!d) return null;
  return {
    ...filingOf(d),
    url: `https://example.invalid/preview/${d.id}`,
    words: d.text.split(/\s+/).length,
    ocr: !!d.ocr,
    text: d.text,
    spans: spansOf(d),
    events: eventsOf(d),
    summary: summaryOf(d),
  };
}

export function previewEvents(window: Window): EventRecord[] {
  const days = WINDOW_DAYS[window];
  const fromDocs = DOCS.filter((d) => d.day < days).flatMap(eventsOf);
  const extra: EventRecord[] = EXTRA_EVENTS.filter(([day]) => day < days).map(([day, type, entityId, headline, source, sentiment], i) => ({
    id: `x-ev${i}`,
    t: isoAt(day, 4),
    type,
    group: EVENT_GROUP[type],
    entityId,
    entityName: NAME.get(entityId)!,
    headline,
    source,
    documentId: "",
    sentiment,
    confidence: +(0.7 + mulberry32(40 + i)() * 0.25).toFixed(2),
    trigger: null,
    arguments: {},
    extractor: i % 3 === 0 ? "rules" : "llm",
  }));
  return [...fromDocs, ...extra].sort((a, b) => b.t.localeCompare(a.t));
}

export function previewOverview(window: Window): Overview {
  const days = WINDOW_DAYS[window];
  const dates = Array.from({ length: days }, (_, i) => isoDay(days - 1 - i));
  const market: MarketPoint[] = dates.map((t) => {
    const vs: number[] = [];
    let n = 0;
    for (const s of series().values()) {
      const p = s.find((x) => x.t === t);
      if (p && p.n > 0) {
        vs.push(p.v);
        n += p.n;
      }
    }
    const mean = vs.reduce((a, b) => a + b, 0) / Math.max(vs.length, 1);
    const std = Math.sqrt(vs.reduce((a, b) => a + (b - mean) ** 2, 0) / Math.max(vs.length, 1));
    return { t, mean: +mean.toFixed(3), std: +std.toFixed(3), n };
  });
  return {
    window,
    corpus: { documents: 1842, entities: 412, events: 236, lastIngestAt: isoAt(0, -0.2) },
    sources: [
      { kind: "BSE", documents: 1187 },
      { kind: "RBI", documents: 284 },
      { kind: "SEBI", documents: 241 },
      { kind: "NEWS", documents: 96 },
      { kind: "NCLT", documents: 34 },
    ],
    market,
    events: previewEvents(window),
    entities: entityRows(window),
    filings: previewFilings(),
  };
}

export const previewCompanies = (window: Window) => entityRows(window);

export function previewCompany(id: string, window: Window): CompanyDetail | null {
  const entity = entityRows(window).find((e) => e.id === id);
  if (!entity) return null;
  const aliases = COMPANIES.find((c) => c[0] === id)![6];
  const mentions: Mention[] = [];
  const claims: Claim[] = [];
  for (const d of DOCS) {
    const sents = sentences(d.text);
    for (const sp of spansOf(d).filter((s) => s.entityId === id)) {
      const s = sents.find((x) => sp.start >= x.start && sp.end <= x.end);
      if (!s) continue;
      mentions.push({
        documentId: d.id,
        documentTitle: d.title,
        source: d.source,
        publishedAt: isoAt(d.day, d.hour),
        sentence: d.text.slice(s.start, s.end),
        start: sp.start - s.start,
        end: sp.end - s.start,
        sentiment: sp.sentiment,
        confidence: sp.confidence,
      });
    }
    if (d.mentions.some((m) => m[1] === id)) claims.push(...(summaryOf(d)?.claims ?? []));
  }
  return {
    entity,
    aliases,
    events: previewEvents("90d").filter((e) => e.entityId === id),
    mentions,
    summary: claims.length ? { id: `${id}-sum`, scope: "entity", model: "llama3.1:8b-instruct + DeBERTa-v3 NLI", generatedAt: isoAt(0, 1), claims } : null,
  };
}

export function previewSearchIndex(): SearchIndex {
  return {
    companies: COMPANIES.map(([id, name, ticker]) => ({ id, name, ticker })),
    filings: DOCS.map((d) => ({ id: d.id, title: d.title, source: d.source })),
  };
}

/** Entities × days matrix of scores for the desktop wallpaper contours. */
export function previewWallpaper(): number[][] {
  const rows = COMPANIES.map(([id]) => series().get(id)!.slice(-90).map((p) => p.v));
  return rows.sort((a, b) => a[a.length - 1] - b[b.length - 1]);
}

export function previewEval(): EvalReport {
  const S = "sentiment" as const;
  return {
    generatedAt: isoAt(1, 2),
    rows: [
      { task: S, model: "FinBERT, entity-marked", baseline: false, dataset: "FinEntity test", indian: false, metrics: { macroF1: 0.84, weightedF1: 0.87, ece: 0.041 } },
      { task: S, model: "FinBERT, entity-marked", baseline: false, dataset: "SEntFiN test", indian: true, metrics: { macroF1: 0.81, weightedF1: 0.85, ece: 0.052 } },
      { task: S, model: "FinBERT, entity-marked", baseline: false, dataset: "FinPulse gold", indian: true, metrics: { macroF1: 0.72, weightedF1: 0.77, ece: 0.068 } },
      { task: S, model: "FinBERT, sentence-level", baseline: true, dataset: "FinEntity test", indian: false, metrics: { macroF1: 0.69, weightedF1: 0.74, ece: 0.093 } },
      { task: S, model: "FinBERT, sentence-level", baseline: true, dataset: "FinPulse gold", indian: true, metrics: { macroF1: 0.58, weightedF1: 0.64, ece: 0.121 } },
      { task: S, model: "TF-IDF + logistic regression", baseline: true, dataset: "FinEntity test", indian: false, metrics: { macroF1: 0.66, weightedF1: 0.71, ece: 0.078 } },
      { task: S, model: "TF-IDF + logistic regression", baseline: true, dataset: "FinPulse gold", indian: true, metrics: { macroF1: 0.55, weightedF1: 0.61, ece: 0.104 } },
      { task: "ner", model: "DeBERTa-v3 token classifier", baseline: false, dataset: "FinEntity test", indian: false, metrics: { spanF1: 0.88, linkAcc: 0.91 } },
      { task: "ner", model: "DeBERTa-v3 token classifier", baseline: false, dataset: "FinPulse gold", indian: true, metrics: { spanF1: 0.79, linkAcc: 0.84 } },
      { task: "ner", model: "CRF + gazetteer", baseline: true, dataset: "FinPulse gold", indian: true, metrics: { spanF1: 0.71, linkAcc: 0.8 } },
      { task: "events", model: "Qwen 2.5 7B, schema-constrained", baseline: false, dataset: "FinPulse gold", indian: true, metrics: { typeF1: 0.76, argF1: 0.63, validity: 0.97 } },
      { task: "events", model: "Rules over BSE categories", baseline: true, dataset: "FinPulse gold", indian: true, metrics: { typeF1: 0.61, argF1: 0.34, validity: 1 } },
      { task: "summaries", model: "Llama 3.1 8B + NLI check", baseline: false, dataset: "FinPulse gold", indian: true, metrics: { rougeL: 0.36, bertScore: 0.88, attribution: 0.86, unsupported: 0.09 } },
      { task: "summaries", model: "Lead-3", baseline: true, dataset: "FinPulse gold", indian: true, metrics: { rougeL: 0.29, bertScore: 0.85, attribution: 1, unsupported: 0 } },
    ],
    confusion: {
      model: "FinBERT, entity-marked",
      dataset: "FinPulse gold",
      labels: ["positive", "neutral", "negative"],
      matrix: [
        [118, 21, 6],
        [24, 162, 19],
        [5, 17, 98],
      ],
    },
    reliability: {
      before: [0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95].map((c, i) => ({ confidence: c, accuracy: Math.max(0, c - [0.02, 0.06, 0.1, 0.12, 0.13, 0.11, 0.08][i]), n: [8, 19, 41, 66, 92, 131, 113][i] })),
      after: [0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95].map((c, i) => ({ confidence: c, accuracy: Math.max(0, c - [0.03, 0.01, -0.02, 0.02, 0.01, 0.03, 0.02][i]), n: [11, 27, 52, 78, 104, 118, 80][i] })),
      eceBefore: 0.094,
      eceAfter: 0.031,
    },
    agreement: [
      { task: "Entity spans", kappa: 0.86, items: 30 },
      { task: "Entity sentiment", kappa: 0.74, items: 30 },
      { task: "Event type", kappa: 0.69, items: 30 },
    ],
  };
}
