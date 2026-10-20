const IN = new Intl.NumberFormat("en-IN");

export const fmtInt = (n: number) => IN.format(n);

/** Shown wherever the pipeline has no value (an unscored company, an undated filing). */
export const NONE = "–";

/** Signed score with a real minus sign, fixed to two places: "+0.24", "−0.31". */
export function fmtScore(v: number | null) {
  if (v === null) return NONE;
  const s = Math.abs(v).toFixed(2);
  if (Number(s) === 0) return "0.00";
  return `${v > 0 ? "+" : "−"}${s}`;
}

export const fmtPct = (v: number | null) => (v === null ? NONE : `${Math.round(v * 100)}%`);

/** Size of a move for ranking; a missing value ranks as no move. */
export const magnitude = (v: number | null) => (v === null ? 0 : Math.abs(v));

const IST_DATE = new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", timeZone: "Asia/Kolkata" });
const IST_DATE_LONG = new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", year: "numeric", timeZone: "Asia/Kolkata" });
const IST_TIME = new Intl.DateTimeFormat("en-IN", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "Asia/Kolkata" });

export const fmtDay = (iso: string | null) => (iso === null ? "undated" : IST_DATE.format(new Date(iso)));
export const fmtDayLong = (iso: string | null) => (iso === null ? "undated" : IST_DATE_LONG.format(new Date(iso)));
export const fmtTime = (iso: string | null) => (iso === null ? NONE : `${IST_TIME.format(new Date(iso))} IST`);

/** Coarse confidence: four segments, because 0.71 and 0.74 are not different readings. */
export const confidenceStep = (c: number | null) => (c === null ? 0 : c >= 0.85 ? 4 : c >= 0.7 ? 3 : c >= 0.55 ? 2 : 1);

export const WINDOW_LABEL = { "7d": "last 7 days", "30d": "last 30 days", "90d": "last 90 days" } as const;
export const WINDOW_DAYS = { "7d": 7, "30d": 30, "90d": 90 } as const;
