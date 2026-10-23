import { NextRequest, NextResponse } from "next/server";

import { SNAPSHOT, readSnapshot, snapshotKey } from "@/lib/api/snapshot";

/**
 * The API of a frozen copy (FINPULSE_SNAPSHOT=1): everything the pages ask for is answered from the recorded
 * data. Ask answers the questions that were recorded; Analyze, speech and an explanation nobody recorded say so
 * plainly instead of pretending to run a model. Without the flag these routes do not exist.
 */
export const dynamic = "force-dynamic";

const FROZEN_NOTE = "This hosted copy is a frozen demonstration of the local application, so it cannot run this step. ";

function refuse(detail: string, status = 503) {
  return NextResponse.json({ detail }, { status });
}

const normalise = (q: string) => q.toLowerCase().replace(/[?\s]+/g, " ").trim();

export async function GET(req: NextRequest, ctx: { params: Promise<{ slug: string[] }> }) {
  if (!SNAPSHOT) return new NextResponse("Not found", { status: 404 });
  const { slug } = await ctx.params;
  const url = `/api/${slug.join("/")}`;
  if (slug[0] === "ask" && slug[1]?.startsWith("rec-")) {
    const job = readSnapshot<Record<string, unknown>>(`/ask-job/${slug[1].slice(4)}`) ?? readSnapshot<Record<string, unknown>>("/ask-job/none");
    return job ? NextResponse.json({ ...job, id: slug[1] }) : refuse("No recorded answer.", 404);
  }
  const hit = readSnapshot(`${url}${req.nextUrl.search}`);
  if (hit !== null) return NextResponse.json(hit);
  if (slug[0] === "documents" && slug[2] === "explain") {
    return refuse(`${FROZEN_NOTE}It explains a sample of mentions; the local build explains any of them.`, 404);
  }
  return refuse("Nothing was recorded for this request.", 404);
}

export async function POST(req: NextRequest, ctx: { params: Promise<{ slug: string[] }> }) {
  if (!SNAPSHOT) return new NextResponse("Not found", { status: 404 });
  const { slug } = await ctx.params;
  if (slug[0] === "ask" && slug.length === 1) {
    const body = (await req.json().catch(() => ({}))) as { question?: string };
    const recorded = readSnapshot<{ key: string }>(`/ask-index/${snapshotKey(normalise(body.question ?? ""))}`);
    return NextResponse.json({ jobId: `rec-${recorded?.key ?? "none"}` });
  }
  if (slug[0] === "analyze") return refuse(`${FROZEN_NOTE}Analyze runs the whole pipeline on a pasted text, which needs the local models.`);
  if (slug[0] === "transcribe") return refuse(`${FROZEN_NOTE}Spoken questions need the local speech model.`);
  return refuse("Unknown request.", 404);
}
