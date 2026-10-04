const IN = new Intl.NumberFormat("en-IN");

export const fmtInt = (n: number) => IN.format(n);

/** Signed score with a real minus sign, fixed to two places: "+0.24", "−0.31". */
export function fmtScore(v: number) {
  const s = Math.abs(v).toFixed(2);
  if (Number(s) === 0) return "0.00";
  return `${v > 0 ? "+" : "−"}${s}`;
}

export const fmtPct = (v: number) => `${Math.round(v * 100)}%`;

const IST_DATE = new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", timeZone: "Asia/Kolkata" });
const IST_DATE_LONG = new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", year: "numeric", timeZone: "Asia/Kolkata" });
const IST_TIME = new Intl.DateTimeFormat("en-IN", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "Asia/Kolkata" });

export const fmtDay = (iso: string) => IST_DATE.format(new Date(iso));
export const fmtDayLong = (iso: string) => IST_DATE_LONG.format(new Date(iso));
export const fmtTime = (iso: string) => `${IST_TIME.format(new Date(iso))} IST`;

/** Coarse confidence: four segments, because 0.71 and 0.74 are not different readings. */
export const confidenceStep = (c: number) => (c >= 0.85 ? 4 : c >= 0.7 ? 3 : c >= 0.55 ? 2 : 1);
