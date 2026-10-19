"""The live path: take one document (pasted text, a PDF, or a URL) through every stage.

Stages are the same as the batch pipeline, run for a single document and reported to the job
row as they finish. A stage that cannot run says why instead of pretending.
"""

from __future__ import annotations

import hashlib
import logging
import time
from collections.abc import Callable
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from finpulse.core.settings import get_settings
from finpulse.db.models import Document, Job
from finpulse.ingest.fetch import FetchRefused, fetch
from finpulse.parse import parse_html
from finpulse.preprocess.clean import clean_pages

from .events import extract_for_document
from .jobs import finish, set_stage
from .link import Linker, link_document
from .parse import ParseResult, apply_parse, parse_raw, parse_text, resolve_raw
from .sentiment import load_scoring_model, score_pending

log = logging.getLogger(__name__)
MAX_TEXT_CHARS = 400_000


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def document_from_text(session: Session, body: str, title: str | None, source: str) -> Document:
    body = body[:MAX_TEXT_CHARS]
    sha = _sha(body.encode("utf-8"))
    existing = session.scalar(select(Document).where(Document.raw_sha256 == sha))
    if existing:
        return existing
    first = next((ln.strip() for ln in body.splitlines() if ln.strip()), "Pasted text")
    doc = Document(
        source_kind=source,
        title=(title or first)[:200],
        raw_sha256=sha,
        clean_text="",
        status="ingested",
        published_at=date.today(),
        meta={"origin": "analyze-text", "text": body},
    )
    session.add(doc)
    session.flush()
    return doc


def document_from_bytes(session: Session, data: bytes, filename: str, source: str) -> Document:
    sha = _sha(data)
    existing = session.scalar(select(Document).where(Document.raw_sha256 == sha))
    if existing:
        return existing
    suffix = ".pdf" if data[:5] == b"%PDF-" else Path(filename).suffix.lower() or ".html"
    relative = Path("uploads") / f"{sha[:16]}{suffix}"
    target = get_settings().raw_dir / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    doc = Document(
        source_kind=source,
        title=Path(filename).stem[:200] or "Uploaded document",
        raw_sha256=sha,
        raw_path=str(relative),
        clean_text="",
        status="ingested",
        published_at=date.today(),
        meta={"origin": "analyze-file", "filename": filename},
    )
    session.add(doc)
    session.flush()
    return doc


def _ingest_url(session: Session, url: str, source: str) -> Document:
    got = fetch(url)
    if got.is_pdf:
        doc = document_from_bytes(
            session, got.body, Path(urlparse(got.url).path).name or "document.pdf", source
        )
    else:
        parsed = parse_html(got.body)
        body = clean_pages(parsed.page_texts)
        if not body.strip():
            raise FetchRefused("no readable text was found on that page")
        doc = document_from_text(session, body, None, source)
    doc.url = got.url
    return doc


def _timed(session: Session, job: Job, key: str, fn: Callable[[], str | None]) -> None:
    set_stage(session, job, key, "running")
    t0 = time.monotonic()
    note = fn()
    set_stage(session, job, key, "done", ms=int((time.monotonic() - t0) * 1000), note=note)


def _skip(session: Session, job: Job, key: str, why: str) -> None:
    set_stage(session, job, key, "skipped", note=why)


def run_analysis(session: Session, job: Job) -> None:
    """Run every stage for the job's document and mark the job done, or raise."""
    payload = job.payload
    state: dict[str, Document | ParseResult] = {}

    def ingest() -> str | None:
        if job.document_id is not None:
            doc = session.get(Document, job.document_id)
        else:
            doc = _ingest_url(session, payload["url"], payload.get("source", "NEWS"))
            job.document_id = doc.id
        assert doc is not None
        state["doc"] = doc
        return "already analysed" if doc.status == "analysed" else None

    set_stage(session, job, "ingest", "running")
    t0 = time.monotonic()
    try:
        note = ingest()
    except FetchRefused as exc:
        set_stage(session, job, "ingest", "failed", note=str(exc))
        job.attempts = job.max_attempts  # a refusal will not change on retry
        finish(session, job, error=str(exc))
        return
    set_stage(session, job, "ingest", "done", ms=int((time.monotonic() - t0) * 1000), note=note)
    doc = state["doc"]
    assert isinstance(doc, Document)

    if doc.status == "analysed":
        for key in ("parse", "entities", "sentiment", "events", "summary", "verify"):
            _skip(session, job, key, "document was already analysed")
        finish(session, job)
        return

    def parse() -> str | None:
        if doc.meta.get("origin") == "analyze-text":
            result = parse_text(doc.meta["text"])
        else:
            result = parse_raw(resolve_raw(doc.raw_path or ""), ocr=True)
        apply_parse(session, doc, result)
        session.commit()
        return f"{doc.n_words} words" + (", OCR" if doc.ocr_used else "")

    _timed(session, job, "parse", parse)

    def entities() -> str | None:
        mentions = link_document(session, Linker(session), doc)
        session.commit()
        return f"{len(mentions)} mentions"

    _timed(session, job, "entities", entities)

    model = load_scoring_model(device="cpu")  # live mode keeps the GPU free for the LLM stages
    if model is None:
        _skip(session, job, "sentiment", "no sentiment model has been trained yet")
    else:

        def sentiment() -> str | None:
            stats = score_pending(session, model, doc_id=doc.id)
            session.execute(text("refresh materialized view entity_daily"))
            session.commit()
            return f"{stats.mentions} mentions scored by {model.version}"

        _timed(session, job, "sentiment", sentiment)

    if doc.source_kind in {"SEBI", "NCLT", "RBI"}:

        def events() -> str | None:
            n = extract_for_document(session, doc)
            session.commit()
            return f"{n} event{'s' if n != 1 else ''} (rules)"

        _timed(session, job, "events", events)
    else:
        _skip(
            session,
            job,
            "events",
            "the rule baseline covers SEBI, NCLT and RBI documents; the LLM stage is not enabled",
        )

    _skip(session, job, "summary", "the summary stage needs the local LLM, which is not enabled yet")
    _skip(session, job, "verify", "nothing to verify without a summary")

    doc.status = "analysed"
    finish(session, job)
