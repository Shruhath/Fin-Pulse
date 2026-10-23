#!/usr/bin/env python3
"""Freeze the local API's answers into web/snapshot/ so the web app can be hosted without the database or the models.

Run with the stack up (`make live`). Writes one gzip file per request, named by the SHA-1 of the path and the sorted
query (the same key `web/src/lib/api/snapshot.ts` uses). The folder holds the text of public orders, so it is
git-ignored and is only ever deployed to the frozen demonstration, never committed.

    scripts/make_snapshot.py            pages, documents, companies, events, evaluation, recorded Ask answers
    scripts/make_snapshot.py --explain  also precompute "Why" explanations for the mentions of a few filings
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

API = os.environ.get("FINPULSE_API_URL", "http://127.0.0.1:8000")
OUT = Path(__file__).resolve().parents[1] / "web" / "snapshot"
WINDOWS = ("7d", "30d", "90d")
FEATURED = (70, 176, 35)  # the Wipro order, the Rajesh Exports order, the Karthik Travels order
EXTRA_QUESTIONS = [
    "Why was KARTHIK TRAVELS PRIVATE LIMITED admitted into insolvency resolution?",
    "What action did SEBI take against Wipro Limited?",
    "What action did SEBI take against Rajesh Exports Limited?",
    "What is the weather in Mumbai today?",
]


def key(path_and_query: str) -> str:
    path, _, query = path_and_query.partition("?")
    q = "&".join(sorted(p for p in query.split("&") if p))
    return hashlib.sha1((f"{path}?{q}" if q else path).encode()).hexdigest()


def normalise(question: str) -> str:
    return re.sub(r"[?\s]+", " ", question.lower()).strip()


def call(path: str, body: dict | None = None, timeout: int = 120):
    req = urllib.request.Request(
        API + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return json.load(res)


def save(path_and_query: str, data) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{key(path_and_query)}.json.gz").write_bytes(gzip.compress(json.dumps(data, ensure_ascii=False).encode()))


def record(path: str) -> object | None:
    try:
        data = call(path)
    except urllib.error.HTTPError as exc:
        print(f"  skipped {path}: HTTP {exc.code}")
        return None
    save(path, data)
    return data


def pages() -> list[dict]:
    for path in ("/api/status", "/api/search/index", "/api/eval", "/api/ask/suggestions"):
        record(path)
    health = call("/api/health")
    save("/api/health", {**health, "ollama": False, "ollamaModels": [], "gpu": None, "asrModel": None, "queuedJobs": 0})
    for w in WINDOWS:
        for path in (f"/api/overview?window={w}", f"/api/entities?window={w}", f"/api/events?window={w}"):
            record(path)
    record("/api/documents")
    docs: list[dict] = []
    page = 1
    while True:
        batch = call(f"/api/documents?page_size=200&page={page}")
        if not batch:
            break
        docs += batch
        page += 1
    slugs: set[str] = {c["id"] for c in json.load(gzip.open(OUT / f"{key('/api/search/index')}.json.gz"))["companies"]}
    for n, doc in enumerate(docs, start=1):
        detail = record(f"/api/documents/{doc['id']}")
        if detail:
            slugs |= {e["id"] for e in detail.get("entities", [])}
        if n % 50 == 0:
            print(f"  documents {n}/{len(docs)}")
    for n, slug in enumerate(sorted(slugs), start=1):
        for w in WINDOWS:
            record(f"/api/entities/{slug}?window={w}")
        if n % 100 == 0:
            print(f"  companies {n}/{len(slugs)}")
    print(f"pages: {len(docs)} documents, {len(slugs)} companies")
    return docs


def recorded_asks() -> None:
    questions = list(dict.fromkeys([*call("/api/ask/suggestions"), *EXTRA_QUESTIONS]))
    weather = None
    for question in questions:
        started = time.time()
        job_id = call("/api/ask", {"question": question})["jobId"]
        while True:
            job = call(f"/api/ask/{job_id}")
            if job["status"] in ("done", "failed"):
                break
            time.sleep(1.5)
        if job["status"] != "done":
            print(f"  not recorded (failed): {question}")
            continue
        digest = key(normalise(question))
        save(f"/ask-job/{digest}", job)
        save(f"/ask-index/{digest}", {"key": digest})
        if job["answer"] and job["answer"].get("abstained"):
            weather = job
        print(f"  recorded in {time.time() - started:.0f} s: {question}")
    if weather is None:
        raise SystemExit("no abstained answer was recorded; the placeholder for other questions needs one")
    answer = {
        **weather["answer"],
        "question": "",
        "reason": "This hosted copy is a frozen demonstration, so only the suggested questions were recorded. "
        "Try one of them, or run the local application to ask anything.",
    }
    save("/ask-job/none", {**weather, "answer": answer})


def explanations(docs: list[dict], per_doc: int) -> None:
    done = refused = 0
    for doc_id in FEATURED:
        detail = call(f"/api/documents/{doc_id}")
        spans = [s for s in detail["spans"] if s.get("entityId") and s.get("sentiment")]
        for span in spans[:per_doc]:
            path = f"/api/documents/{doc_id}/explain?start={span['start']}&end={span['end']}"
            try:
                save(path, call(path, timeout=300))
                done += 1
            except urllib.error.HTTPError:
                refused += 1  # the model could not read this mention; the page says so
        print(f"  explanations for document {doc_id}: {done} saved, {refused} refused so far")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--explain", action="store_true", help="also precompute the Why explanations (CPU, several minutes)")
    ap.add_argument("--per-doc", type=int, default=45)
    ap.add_argument("--skip-pages", action="store_true")
    args = ap.parse_args()
    docs: list[dict] = []
    if not args.skip_pages:
        docs = pages()
    print("recording Ask answers")
    recorded_asks()
    if args.explain:
        print("precomputing explanations")
        explanations(docs, args.per_doc)
    size = sum(f.stat().st_size for f in OUT.glob("*.json.gz"))
    print(f"snapshot: {len(list(OUT.glob('*.json.gz')))} files, {size / 1e6:.1f} MB in {OUT}")
