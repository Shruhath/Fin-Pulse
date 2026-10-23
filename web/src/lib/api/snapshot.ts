import "server-only";

import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { gunzipSync } from "node:zlib";

/**
 * A frozen copy of the API's answers, one gzip file per request, written by `scripts/make_snapshot.py`. It lets the
 * application be hosted without the database or the models. The key is the SHA-1 of the path and the sorted query.
 */
export const SNAPSHOT = process.env.FINPULSE_SNAPSHOT === "1";
const DIR = path.join(process.cwd(), "snapshot");

export function snapshotKey(pathAndQuery: string): string {
  const [p, q = ""] = pathAndQuery.split("?");
  const query = q.split("&").filter(Boolean).sort().join("&");
  return createHash("sha1").update(query ? `${p}?${query}` : p).digest("hex");
}

/** The recorded answer to `pathAndQuery`, or null when nothing was recorded for it. */
export function readSnapshot<T = unknown>(pathAndQuery: string): T | null {
  const file = path.join(DIR, `${snapshotKey(pathAndQuery)}.json.gz`);
  if (!existsSync(file)) return null;
  return JSON.parse(gunzipSync(readFileSync(file)).toString("utf8")) as T;
}
