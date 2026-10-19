"""Parse stage: raw file -> clean text, sentences, status 'parsed'.

`parse_raw` is pure (no database) so it can run on a thread pool; the main thread writes
each result and commits, so an interrupted run keeps everything finished so far.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from finpulse.core.offsets import Span
from finpulse.core.settings import get_settings
from finpulse.db.models import Document, Sentence
from finpulse.parse import parse_file
from finpulse.parse.ocr import tesseract_version
from finpulse.preprocess.clean import clean_pages, clean_text
from finpulse.preprocess.sentences import split_sentences

from .runs import recorded_run

log = logging.getLogger(__name__)


@dataclass(slots=True)
class ParseResult:
    clean_text: str
    n_pages: int
    ocr_pages: int
    sentences: list[Span]


@dataclass(slots=True)
class ParseStats:
    parsed: int = 0
    failed: int = 0
    ocr_documents: int = 0


def resolve_raw(raw_path: str) -> Path:
    """Raw files live under the collector output or the app's own raw store."""
    cfg = get_settings()
    for base in (cfg.corpus_dir, cfg.raw_dir):
        candidate = base / raw_path
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(raw_path)


def parse_raw(path: Path, *, ocr: bool = True) -> ParseResult:
    parsed = parse_file(path, ocr=ocr)
    text = clean_pages(parsed.page_texts)
    return ParseResult(
        clean_text=text,
        n_pages=len(parsed.pages),
        ocr_pages=sum(p.ocr for p in parsed.pages),
        sentences=split_sentences(text),
    )


def parse_text(text: str) -> ParseResult:
    """Pasted text has no pages or layout: clean it and split it."""
    cleaned = clean_text(text)
    return ParseResult(cleaned, 1, 0, split_sentences(cleaned))


def apply_parse(session: Session, doc: Document, result: ParseResult) -> None:
    doc.clean_text = result.clean_text
    doc.n_words = len(result.clean_text.split())
    doc.n_pages = result.n_pages
    doc.ocr_used = result.ocr_pages > 0
    doc.status = "parsed"
    doc.meta = {**doc.meta, "ocr_pages": result.ocr_pages}
    session.execute(delete(Sentence).where(Sentence.doc_id == doc.id))
    session.add_all(
        Sentence(doc_id=doc.id, idx=i, char_start=s.start, char_end=s.end, text=s.slice(result.clean_text))
        for i, s in enumerate(result.sentences)
    )


def parse_pending(
    session: Session,
    *,
    workers: int = 4,
    limit: int | None = None,
    ocr: bool = True,
    redo: bool = False,
    progress: Callable[[int, int, Document], None] | None = None,
) -> ParseStats:
    """Parse every document still in status 'ingested', or every stored document with `redo`."""
    stmt = select(Document).order_by(Document.id)
    if not redo:
        stmt = stmt.where(Document.status == "ingested")
    if limit:
        stmt = stmt.limit(limit)
    docs = list(session.scalars(stmt))
    stats = ParseStats()
    if not docs:
        return stats

    with recorded_run(
        session,
        "parse",
        model=f"pymupdf+tesseract {tesseract_version() or 'absent'}",
        params={"documents": len(docs), "ocr": ocr, "dpi": get_settings().ocr_dpi},
    ):
        by_future = {}
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            for doc in docs:
                if doc.meta.get("text") and not doc.raw_path:  # RSS items and pasted text arrive as text
                    by_future[pool.submit(parse_text, doc.meta["text"])] = doc
                    continue
                try:
                    path = resolve_raw(doc.raw_path or "")
                except FileNotFoundError:
                    doc.status = "failed"
                    doc.meta = {**doc.meta, "error": "raw file not found"}
                    stats.failed += 1
                    continue
                by_future[pool.submit(parse_raw, path, ocr=ocr)] = doc
            for done, fut in enumerate(as_completed(by_future), start=1):
                doc = by_future[fut]
                try:
                    result = fut.result()
                except Exception as exc:
                    log.warning("parse failed for %s: %s", doc.title, exc)
                    doc.status = "failed"
                    doc.meta = {**doc.meta, "error": f"{type(exc).__name__}: {exc}"[:500]}
                    stats.failed += 1
                else:
                    apply_parse(session, doc, result)
                    stats.parsed += 1
                    stats.ocr_documents += result.ocr_pages > 0
                session.commit()
                if progress:
                    progress(done, len(by_future), doc)
    session.commit()
    return stats
