#!/usr/bin/env python3
"""Fetch layer 2: Indian regulatory and tribunal documents into data-set/layer2.

Sources (public, no login, no captcha):
  - IBBI's mirror of NCLT orders (ibbi.gov.in/orders/nclt): "Admission - Final order" PDFs
  - SEBI enforcement orders (sebi.gov.in): Adjudicating Officer, Chairperson/Members, Settlement

Polite by design: one request at a time, at most about one per second, an identifying
User-Agent, retries only on server errors, and an immediate stop (no evasion) if a site
answers 403/418/429. Safe to re-run: documents already in the index are skipped.

  ./scripts/fetch_layer2.py --test             tiny run into data-set/layer2-test
  ./scripts/fetch_layer2.py                    full run (about 260 documents)
  ./scripts/fetch_layer2.py --only ibbi        one source
  ./scripts/fetch_layer2.py --ibbi 30 --sebi-ao 60 --sebi-wtm 25 --sebi-settlement 15

Raw documents stay private (data-set/ is git-ignored). See the README written into the output
folder for the reuse terms of each source.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UA = "FinPulse-NLP-course-project (+https://github.com/Shruhath/Fin-Pulse)"
MAX_PDF_BYTES = 30 * 1024 * 1024
SCANNED_WORDS_PER_PAGE = 20  # under this, the PDF has no usable text layer

IBBI_LIST = "https://ibbi.gov.in/orders/nclt"
SEBI_BASE = "https://www.sebi.gov.in"
SEBI_AJAX = SEBI_BASE + "/sebiweb/ajax/home/getnewslistinfo.jsp"
SEBI_CATS = {
    "ao": (6, "Orders of AO"),
    "wtm": (2, "Orders of Chairperson/Members"),
    "settlement": (3, "Settlement Order"),
}


class Blocked(Exception):
    """The site refused us. We stop; we never try to get around it."""


class Client:
    def __init__(self, delay: float) -> None:
        self.delay = delay
        self.last = 0.0
        self.requests = 0

    def get(self, url: str, *, data: bytes | None = None, headers: dict | None = None,
            max_bytes: int = 5 * 1024 * 1024, timeout: int = 60) -> tuple[int, bytes]:
        for attempt in range(3):
            wait = self.delay - (time.monotonic() - self.last)
            if wait > 0:
                time.sleep(wait + random.uniform(0, 0.3))
            req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, **(headers or {})})
            try:
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    body = r.read(max_bytes + 1)
                    self.last = time.monotonic()
                    self.requests += 1
                    return r.status, body
            except urllib.error.HTTPError as e:
                self.last = time.monotonic()
                if e.code in (403, 418, 429):
                    raise Blocked(f"{e.code} from {urllib.parse.urlparse(url).netloc}") from e
                if e.code >= 500:
                    time.sleep(3 * (attempt + 1))
                    continue
                return e.code, b""
            except (urllib.error.URLError, TimeoutError, ConnectionError):
                self.last = time.monotonic()
                time.sleep(3 * (attempt + 1))
        return 0, b""


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def clean(html: str) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", html))).strip()


def parse_date(s: str, fmts: tuple[str, ...]) -> str:
    for f in fmts:
        try:
            return datetime.strptime(s.strip(), f).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return ""


def spaced(n_total: int, n: int) -> list[int]:
    """n page indexes spread evenly over 0..n_total-1 (always includes the newest)."""
    if n_total <= n:
        return list(range(n_total))
    return sorted({round(i * (n_total - 1) / (n - 1)) for i in range(n)})


def round_robin(groups: list[list[dict]], target: int) -> list[dict]:
    out, i = [], 0
    while len(out) < target and any(groups):
        g = groups[i % len(groups)]
        if g:
            out.append(g.pop(0))
        i += 1
    return out


# ---------------------------------------------------------------- storage
class Store:
    def __init__(self, base: Path) -> None:
        self.base = base
        (base / "pdf").mkdir(parents=True, exist_ok=True)
        (base / "text").mkdir(exist_ok=True)
        self.index_path = base / "index.jsonl"
        self.seen: set[str] = set()
        if self.index_path.exists():
            for line in self.index_path.read_text().splitlines():
                if line.strip():
                    self.seen.add(json.loads(line)["url"])

    def add(self, rec: dict) -> None:
        with self.index_path.open("a") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        self.seen.add(rec["url"])

    def save_pdf(self, key: str, body: bytes) -> tuple[Path, Path, dict]:
        pdf = self.base / "pdf" / f"{key}.pdf"
        pdf.write_bytes(body)
        txt = self.base / "text" / f"{key}.txt"
        stats = {"pages": 0, "words": 0, "text_layer": False}
        try:
            info = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True, timeout=60).stdout
            m = re.search(r"Pages:\s+(\d+)", info)
            stats["pages"] = int(m.group(1)) if m else 0
            subprocess.run(["pdftotext", "-layout", str(pdf), str(txt)], capture_output=True, timeout=120)
            words = len(txt.read_text(errors="ignore").split()) if txt.exists() else 0
            stats["words"] = words
            stats["text_layer"] = stats["pages"] > 0 and words / stats["pages"] >= SCANNED_WORDS_PER_PAGE
        except (OSError, subprocess.SubprocessError):
            pass
        return pdf, txt, stats


def doc_key(source: str, date: str, url: str) -> str:
    return f"{source}_{date or 'undated'}_{hashlib.sha1(url.encode()).hexdigest()[:10]}"


# ---------------------------------------------------------------- IBBI / NCLT
IBBI_ROW = re.compile(
    r"<tr>\s*<td>\s*\d+\s*</td>\s*<td>\s*([^<]+?)\s*</td>\s*<td>\s*<a href=[\"']?([^\"'\s>]+)[^>]*>(.*?)</a>\s*</td>\s*<td>\s*([^<]*?)\s*</td>",
    re.S,
)


def ibbi_page(c: Client, page: int) -> tuple[list[dict], int]:
    url = IBBI_LIST if page == 0 else f"{IBBI_LIST}?page={page}"
    status, body = c.get(url)
    if status != 200:
        return [], 0
    html = body.decode("utf-8", "ignore")
    last = max([int(x) for x in re.findall(r"page=(\d+)", html)] or [0])
    rows = []
    for date, href, subject, remark in IBBI_ROW.findall(html):
        title = re.sub(r"\(\s*[\d.]+\s*(?:KB|MB)\s*\)\s*$", "", clean(subject)).strip()
        rows.append({
            "date": parse_date(date, ("%d %b, %Y", "%d %B, %Y")),
            "title": title,
            "label": clean(remark),
            "url": urllib.parse.urljoin("https://ibbi.gov.in", href),
            "list_page": page,
        })
    return rows, last


def is_admission(label: str) -> bool:
    """Recent orders say 'Admission - Final order'; older ones just 'ADMITTED'."""
    return bool(re.search(r"\badmitted\b|\badmission\b.*\bfinal\b", label, re.I))


def fetch_ibbi(c: Client, dest: Path, target: int, n_pages: int) -> dict:
    store = Store(dest / "ibbi_nclt")
    _, last = ibbi_page(c, 0)
    pages = spaced(last + 1, n_pages) if last else [0]
    print(f"[ibbi] listing has {last + 1} pages; sampling {len(pages)} spread across 2017 to now", flush=True)
    seen_rows, groups = [], []
    for p in pages:
        rows, _ = ibbi_page(c, p)
        seen_rows += rows
        groups.append([r for r in rows if is_admission(r["label"])])
    with (store.base / "listing_index.jsonl").open("w") as f:
        for r in seen_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    labels: dict[str, int] = {}
    for r in seen_rows:
        labels[r["label"]] = labels.get(r["label"], 0) + 1
    print(f"[ibbi] listing rows seen: {len(seen_rows)}; admission-final candidates: {sum(map(len, groups))}", flush=True)

    got = skipped = failed = 0
    for r in round_robin(groups, target):
        if r["url"] in store.seen:
            skipped += 1
            continue
        status, body = c.get(r["url"], max_bytes=MAX_PDF_BYTES, timeout=120)
        if status != 200 or not body.startswith(b"%PDF") or len(body) > MAX_PDF_BYTES:
            failed += 1
            print(f"[ibbi] failed ({status}): {r['title'][:70]}", flush=True)
            continue
        key = doc_key("ibbi_nclt", r["date"], r["url"])
        pdf, txt, st = store.save_pdf(key, body)
        store.add({**r, "source": "ibbi_nclt", "category": "nclt_admission_final", "file": str(pdf.relative_to(dest)),
                   "text_file": str(txt.relative_to(dest)), "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(),
                   "retrieved_at": now(), **st})
        got += 1
        print(f"[ibbi] {got}/{target} {r['date']} {st['pages']}p {'text' if st['text_layer'] else 'SCAN'} {r['title'][:60]}", flush=True)
    return {"source": "ibbi_nclt", "downloaded": got, "skipped": skipped, "failed": failed, "label_counts": labels}


# ---------------------------------------------------------------- SEBI
def sebi_list(c: Client, smid: int, sm_text: str, page: int) -> tuple[list[dict], int]:
    form = urllib.parse.urlencode({
        "nextValue": 1, "next": "n", "search": "", "fromDate": "", "toDate": "", "fromYear": "", "toYear": "",
        "deptId": "", "sid": 2, "ssid": 9, "smid": smid, "ssidhidden": 9, "intmid": -1,
        "sText": "Enforcement", "ssText": "Orders", "smText": sm_text, "doDirect": page,
    }).encode()
    status, body = c.get(
        SEBI_AJAX, data=form,
        headers={"Content-Type": "application/x-www-form-urlencoded",
                 "Referer": f"{SEBI_BASE}/sebiweb/home/HomeAction.do?doListing=yes&sid=2&ssid=9&smid={smid}"},
    )
    if status != 200:
        return [], 0
    html = body.decode("utf-8", "ignore")
    m = re.search(r"of\s+([\d,]+)\s+records", html)
    total = int(m.group(1).replace(",", "")) if m else 0
    rows = []
    for block in html.split("</tr>"):
        d = re.search(r"<td>\s*([A-Z][a-z]{2} \d{2}, \d{4})\s*</td>", block)
        a = re.search(r"<a href='(https://www\.sebi\.gov\.in/enforcement/[^']+)'[^>]*class='points'>(.*?)</a>", block, re.S)
        if d and a:
            title = clean(a.group(2).split("<br")[0])
            if not STUB_TITLE.search(title):
                rows.append({"date": parse_date(d.group(1), ("%b %d, %Y",)), "title": title, "url": a.group(1), "list_page": page})
    return rows, total


def sebi_pdf_url(html: str) -> str | None:
    """The order page embeds the PDF as ?file=<url or /relative/path>.pdf (older pages use a relative path)."""
    m = re.search(r"file=([^\"'&\s]+\.pdf)", html, re.I) or re.search(r"[\"']((?:https?://|/)[^\"']+\.pdf)[\"']", html, re.I)
    return urllib.parse.urljoin(SEBI_BASE + "/", m.group(1)) if m else None


STUB_TITLE = re.compile(r"\b(corrigendum|addendum|erratum)\b", re.I)  # one-page amendments, no content


def fetch_sebi(c: Client, dest: Path, targets: dict[str, int], n_pages: int) -> list[dict]:
    store = Store(dest / "sebi_orders")
    results = []
    for cat, target in targets.items():
        if target <= 0:
            continue
        smid, sm_text = SEBI_CATS[cat]
        rows0, total = sebi_list(c, smid, sm_text, 0)
        pages_total = math.ceil(total / 25) if total else 1
        pages = spaced(pages_total, n_pages)
        print(f"[sebi/{cat}] {total} orders over {pages_total} pages; sampling {len(pages)} pages", flush=True)
        groups = [rows0] if 0 in pages else []
        for p in pages:
            if p == 0:
                continue
            rows, _ = sebi_list(c, smid, sm_text, p)
            groups.append(rows)
        got = skipped = failed = html_only = 0
        for r in round_robin([list(g) for g in groups], target):
            if r["url"] in store.seen:
                skipped += 1
                continue
            status, body = c.get(r["url"])
            if status != 200:
                failed += 1
                continue
            page_html = body.decode("utf-8", "ignore")
            pdf_url = sebi_pdf_url(page_html)
            key = doc_key("sebi_" + cat, r["date"], r["url"])
            if pdf_url:
                status, pdf_body = c.get(pdf_url, max_bytes=MAX_PDF_BYTES, timeout=120)
                if status != 200 or not pdf_body.startswith(b"%PDF") or len(pdf_body) > MAX_PDF_BYTES:
                    failed += 1
                    print(f"[sebi/{cat}] failed ({status}): {r['title'][:70]}", flush=True)
                    continue
                pdf, txt, st = store.save_pdf(key, pdf_body)
                rec = {**r, "source": "sebi_orders", "category": cat, "pdf_url": pdf_url, "file": str(pdf.relative_to(dest)),
                       "text_file": str(txt.relative_to(dest)), "bytes": len(pdf_body),
                       "sha256": hashlib.sha256(pdf_body).hexdigest(), "retrieved_at": now(), **st}
                shown = f"{st['pages']}p {'text' if st['text_layer'] else 'SCAN'}"
            else:
                # older orders are inline HTML: keep the page text instead
                txt = store.base / "text" / f"{key}.txt"
                body_text = clean(re.sub(r"<script.*?</script>|<style.*?</style>", " ", page_html, flags=re.S))
                txt.write_text(body_text)
                rec = {**r, "source": "sebi_orders", "category": cat, "pdf_url": None, "file": None,
                       "text_file": str(txt.relative_to(dest)), "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(),
                       "retrieved_at": now(), "pages": 0, "words": len(body_text.split()), "text_layer": True, "html_only": True}
                html_only += 1
                shown = "html"
            store.add(rec)
            got += 1
            print(f"[sebi/{cat}] {got}/{target} {r['date']} {shown} {r['title'][:55]}", flush=True)
        results.append({"source": f"sebi_{cat}", "orders_in_listing": total, "downloaded": got, "skipped": skipped,
                        "failed": failed, "html_only": html_only})
    return results


# ---------------------------------------------------------------- reporting
README = """Layer 2: regulatory and tribunal documents (raw, private; never commit this folder).

ibbi_nclt/     NCLT orders mirrored by IBBI (ibbi.gov.in/orders/nclt), "Admission - Final order" only.
               Terms (IBBI Copyright Policy, paraphrased from the research notes): reproduction free of charge,
               in any format, without specific permission, with accuracy and attribution. Orders are "not certified copies".
sebi_orders/   SEBI enforcement orders (sebi.gov.in/enforcement/orders): ao, wtm, settlement.
               Terms: reproduction is allowed "after taking proper permission by sending a mail". We keep these
               private for research and publish only labels, offsets and hashes until that permission arrives.
               Orders can contain PAN numbers and addresses of individuals: mask them before any use beyond this folder.

index.jsonl in each folder: one record per document (url, title, date, label/category, sha256, pages, words, text_layer).
text_layer=false means the PDF is a scan with no usable text: it needs OCR before NLP.
pdf/ original files, text/ pdftotext output (empty for scans).
"""


def summarize(dest: Path) -> None:
    print("\n=== summary ===")
    for sub in ("ibbi_nclt", "sebi_orders"):
        idx = dest / sub / "index.jsonl"
        if not idx.exists():
            continue
        recs = [json.loads(line) for line in idx.read_text().splitlines() if line.strip()]
        scans = [r for r in recs if not r.get("text_layer")]
        size = sum(r.get("bytes", 0) for r in recs) / 1e6
        cats: dict[str, int] = {}
        for r in recs:
            cats[r["category"]] = cats.get(r["category"], 0) + 1
        years = sorted(r["date"][:4] for r in recs if r.get("date"))
        print(f"{sub}: {len(recs)} docs, {size:.0f} MB, {len(scans)} need OCR ({100 * len(scans) // max(len(recs), 1)}%), "
              f"years {years[0] if years else '-'}..{years[-1] if years else '-'}, by category {cats}")
    print(f"output: {dest}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dest", type=Path, default=None)
    ap.add_argument("--only", choices=["ibbi", "sebi"])
    ap.add_argument("--ibbi", type=int, default=60, help="NCLT admission orders to download")
    ap.add_argument("--ibbi-pages", type=int, default=40, help="listing pages sampled across the date range")
    ap.add_argument("--sebi-ao", type=int, default=120)
    ap.add_argument("--sebi-wtm", type=int, default=50)
    ap.add_argument("--sebi-settlement", type=int, default=30)
    ap.add_argument("--sebi-pages", type=int, default=14, help="listing pages sampled per SEBI category")
    ap.add_argument("--delay", type=float, default=1.2, help="minimum seconds between requests")
    ap.add_argument("--test", action="store_true", help="tiny run into data-set/layer2-test")
    a = ap.parse_args()

    if a.test:
        a.ibbi, a.ibbi_pages, a.sebi_ao, a.sebi_wtm, a.sebi_settlement, a.sebi_pages = 3, 4, 2, 2, 2, 3
    dest = a.dest or ROOT / "data-set" / ("layer2-test" if a.test else "layer2")
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "README.txt").write_text(README)
    c = Client(max(a.delay, 1.0))
    report: list[dict] = []
    try:
        if a.only in (None, "ibbi"):
            report.append(fetch_ibbi(c, dest, a.ibbi, a.ibbi_pages))
        if a.only in (None, "sebi"):
            report += fetch_sebi(c, dest, {"ao": a.sebi_ao, "wtm": a.sebi_wtm, "settlement": a.sebi_settlement}, a.sebi_pages)
    except Blocked as e:
        print(f"\nSTOPPED: {e}. The site refused us, so we stop and do not retry or work around it.", file=sys.stderr)
        summarize(dest)
        return 2
    (dest / "run_report.json").write_text(json.dumps({"finished": now(), "requests": c.requests, "results": report}, indent=2))
    summarize(dest)
    print(f"requests made: {c.requests}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
