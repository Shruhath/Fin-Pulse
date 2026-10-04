/**
 * SYNTHETIC PREVIEW DATA, not model output.
 *
 * Deterministic fixtures used only when FINPULSE_PREVIEW=1, so the interface
 * can be designed before the pipeline produces real readings. Company names are
 * real listed companies purely for layout realism; every score, event and
 * headline below is invented and must never be presented as a finding.
 */

import type {
  EntityRow,
  EventMarker,
  EventType,
  FilingItem,
  MarketPoint,
  Overview,
  SentimentLabel,
  SourceKind,
  Window,
} from "@/lib/api/types";
import { EVENT_GROUP } from "@/lib/api/types";

const AS_OF = Date.UTC(2026, 9, 3); // 3 Oct 2026
const DAY = 86_400_000;
const HISTORY = 180;

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

const iso = (offset: number) => new Date(AS_OF - offset * DAY).toISOString().slice(0, 10);
const clamp = (v: number) => Math.max(-1, Math.min(1, v));
const label = (v: number): SentimentLabel => (v > 0.12 ? "positive" : v < -0.12 ? "negative" : "neutral");

// [id, name, ticker, sector, drift target, volatility]
const SEED: [string, string, string, string, number, number][] = [
  ["reliance", "Reliance Industries", "RELIANCE", "Energy", 0.18, 0.09],
  ["hdfcbank", "HDFC Bank", "HDFCBANK", "Banking", 0.12, 0.07],
  ["icicibank", "ICICI Bank", "ICICIBANK", "Banking", 0.22, 0.07],
  ["sbin", "State Bank of India", "SBIN", "Banking", 0.05, 0.08],
  ["infy", "Infosys", "INFY", "IT Services", -0.24, 0.1],
  ["tcs", "Tata Consultancy Services", "TCS", "IT Services", 0.08, 0.06],
  ["wipro", "Wipro", "WIPRO", "IT Services", -0.12, 0.09],
  ["yesbank", "Yes Bank", "YESBANK", "Banking", -0.31, 0.12],
  ["bajfinance", "Bajaj Finance", "BAJFINANCE", "NBFC", -0.18, 0.11],
  ["paytm", "One 97 Communications", "PAYTM", "Fintech", -0.42, 0.13],
  ["sunpharma", "Sun Pharmaceutical", "SUNPHARMA", "Pharma", 0.26, 0.08],
  ["drreddy", "Dr. Reddy's Laboratories", "DRREDDY", "Pharma", 0.14, 0.09],
  ["tatamotors", "Tata Motors", "TATAMOTORS", "Auto", 0.31, 0.1],
  ["maruti", "Maruti Suzuki", "MARUTI", "Auto", 0.09, 0.07],
  ["adaniports", "Adani Ports & SEZ", "ADANIPORTS", "Infrastructure", -0.08, 0.14],
  ["lt", "Larsen & Toubro", "LT", "Infrastructure", 0.27, 0.07],
  ["zeel", "Zee Entertainment", "ZEEL", "Media", -0.36, 0.13],
  ["vedl", "Vedanta", "VEDL", "Metals", -0.21, 0.12],
  ["itc", "ITC", "ITC", "FMCG", 0.11, 0.05],
  ["hul", "Hindustan Unilever", "HINDUNILVR", "FMCG", 0.02, 0.05],
];

type Series = { t: string; v: number; n: number }[];

function buildSeries(): Map<string, Series> {
  const out = new Map<string, Series>();
  SEED.forEach(([id, , , , target, vol], i) => {
    const rnd = mulberry32(1000 + i * 97);
    let v = target * 0.4;
    const s: Series = [];
    for (let d = HISTORY - 1; d >= 0; d--) {
      // mean-reverting walk toward the seeded target
      v = clamp(v + 0.18 * (target - v) + (rnd() - 0.5) * vol * 2);
      const n = rnd() < 0.18 ? 0 : 1 + Math.floor(rnd() * 6);
      s.push({ t: iso(d), v: +v.toFixed(3), n });
    }
    out.set(id, s);
  });
  return out;
}

const EVENTS: [number, EventType, string, string, SourceKind][] = [
  [2, "SEBI Penalty", "paytm", "SEBI levies ₹1.2 crore penalty over disclosure lapses in related-party transactions", "SEBI"],
  [3, "New Contract", "lt", "Wins order worth ₹2,500–5,000 crore for a metro rail package", "BSE"],
  [5, "RBI Action", "yesbank", "RBI imposes monetary penalty for non-compliance with KYC directions", "RBI"],
  [6, "Guidance Change", "infy", "Narrows FY27 revenue guidance to 1–2% in constant currency", "BSE"],
  [9, "Regular Dividend", "itc", "Board recommends interim dividend of ₹6.50 per share", "BSE"],
  [11, "Auditor Resignation", "zeel", "Statutory auditor resigns citing information access concerns", "BSE"],
  [14, "Acquisition", "sunpharma", "Completes acquisition of a US specialty dermatology portfolio", "BSE"],
  [17, "Pledge Invocation", "vedl", "Lender invokes pledge on 2.1% of promoter shareholding", "BSE"],
  [20, "Dividend Increase", "tcs", "Raises interim dividend to ₹11 per share", "BSE"],
  [23, "NCLT Admission", "adaniports", "NCLT admits insolvency petition against a subsidiary's contractor", "NCLT"],
  [26, "Stock Repurchase", "wipro", "Board approves buyback of up to ₹12,000 crore", "BSE"],
  [33, "SEBI Penalty", "bajfinance", "SEBI settlement order on delayed disclosure of a credit rating action", "SEBI"],
  [41, "RBI Action", "bajfinance", "RBI lifts restrictions on two digital lending products", "RBI"],
  [52, "Clinical Trial", "drreddy", "Phase III trial of a biosimilar meets its primary endpoint", "BSE"],
  [64, "Special Dividend", "maruti", "Declares special dividend alongside quarterly results", "BSE"],
  [77, "Dividend Cut", "vedl", "Reduces interim dividend as commodity margins compress", "BSE"],
];

const FILINGS: [number, string, SourceKind, [string, SentimentLabel][], FilingItem["status"]][] = [
  [0, "Adjudication order in respect of One 97 Communications Ltd", "SEBI", [["paytm", "negative"]], "analysed"],
  [0, "Outcome of board meeting: interim dividend and Q2 results", "BSE", [["itc", "positive"]], "analysed"],
  [1, "Award of order: metro rail elevated viaduct package", "BSE", [["lt", "positive"]], "analysed"],
  [1, "RBI imposes monetary penalty on Yes Bank Ltd", "RBI", [["yesbank", "negative"]], "analysed"],
  [2, "Revision of revenue guidance and analyst call transcript", "BSE", [["infy", "negative"], ["tcs", "neutral"]], "analysed"],
  [2, "Resignation of statutory auditor: Regulation 30 disclosure", "BSE", [["zeel", "negative"]], "analysed"],
  [3, "Completion of acquisition of specialty portfolio", "BSE", [["sunpharma", "positive"], ["drreddy", "neutral"]], "analysed"],
  [3, "Disclosure of invocation of pledged shares", "BSE", [["vedl", "negative"]], "analysed"],
  [4, "Order under Section 7 of the Insolvency and Bankruptcy Code", "NCLT", [["adaniports", "negative"]], "parsed"],
  [4, "Press release: monthly sales update for September", "BSE", [["tatamotors", "positive"], ["maruti", "positive"]], "analysed"],
  [5, "Settlement order: delayed disclosure of rating action", "SEBI", [["bajfinance", "negative"]], "analysed"],
  [5, "Intimation of buyback through tender offer", "BSE", [["wipro", "positive"]], "ingested"],
];

const WINDOW_DAYS: Record<Window, number> = { "7d": 7, "30d": 30, "90d": 90 };

export function previewOverview(window: Window): Overview {
  const days = WINDOW_DAYS[window];
  const series = buildSeries();
  const names = new Map(SEED.map(([id, name]) => [id, name]));

  const dates = Array.from({ length: days }, (_, i) => iso(days - 1 - i));
  const market: MarketPoint[] = dates.map((t) => {
    const vs: number[] = [];
    let n = 0;
    for (const s of series.values()) {
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

  const entities: EntityRow[] = SEED.map(([id, name, ticker, sector], i) => {
    const s = series.get(id)!;
    const cur = s.slice(-days).filter((p) => p.n > 0);
    const prev = s.slice(-2 * days, -days).filter((p) => p.n > 0);
    const avg = (xs: typeof s) => xs.reduce((a, p) => a + p.v, 0) / Math.max(xs.length, 1);
    const score = +avg(cur).toFixed(2);
    const rnd = mulberry32(7 + i);
    return {
      id,
      name,
      ticker,
      sector,
      score,
      delta: +(score - avg(prev)).toFixed(2),
      sentiment: label(score),
      mentions: cur.reduce((a, p) => a + p.n, 0),
      confidence: +(0.62 + rnd() * 0.3).toFixed(2),
      series: s.slice(-days).map(({ t, v }) => ({ t, v })),
    };
  });

  const events: EventMarker[] = EVENTS.filter(([d]) => d < days).map(([d, type, entityId, headline, source], i) => ({
    id: `ev-${i}`,
    t: iso(d),
    type,
    group: EVENT_GROUP[type],
    entityId,
    entityName: names.get(entityId)!,
    headline,
    source,
    documentId: `doc-${i}`,
  }));

  const filings: FilingItem[] = FILINGS.map(([d, title, source, ents, status], i) => ({
    id: `doc-f${i}`,
    title,
    source,
    publishedAt: new Date(AS_OF - d * DAY - (i % 4) * 3_600_000 * 2.5).toISOString(),
    entities: ents.map(([id, sentiment]) => ({ id, name: names.get(id)!, sentiment })),
    status,
  }));

  return {
    window,
    corpus: { documents: 1842, entities: 412, events: 236, lastIngestAt: new Date(AS_OF + 6.2 * 3_600_000).toISOString() },
    sources: [
      { kind: "BSE", documents: 1187 },
      { kind: "RBI", documents: 284 },
      { kind: "SEBI", documents: 241 },
      { kind: "NEWS", documents: 96 },
      { kind: "NCLT", documents: 34 },
    ],
    market,
    events,
    entities,
    filings,
  };
}
