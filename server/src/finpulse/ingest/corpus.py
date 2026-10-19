"""Load the layer 2 collector output (`data-set/layer2`) into the `documents` table.

Documents are keyed by the SHA-256 of the file the collector saved, so running this twice,
or after a re-collection, never duplicates anything.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from finpulse.db.models import Document

log = logging.getLogger(__name__)

SOURCE_KIND = {"sebi_orders": "SEBI", "ibbi_nclt": "NCLT"}
DOC_TYPE = {
    "ao": "SEBI adjudication order",
    "wtm": "SEBI whole-time member order",
    "settlement": "SEBI settlement order",
    "nclt_admission_final": "NCLT admission order",
}


@dataclass(slots=True)
class IngestStats:
    seen: int = 0
    created: int = 0
    existing: int = 0
    missing_file: int = 0
    by_source: dict[str, int] = field(default_factory=dict)


def iter_records(corpus_dir: Path, sources: set[str] | None = None) -> Iterator[dict[str, Any]]:
    for src_dir in sorted(p for p in corpus_dir.iterdir() if (p / "index.jsonl").is_file()):
        if src_dir.name not in SOURCE_KIND or (sources and src_dir.name not in sources):
            continue
        with (src_dir / "index.jsonl").open(encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    yield json.loads(line)


def ingest_corpus(
    session: Session,
    corpus_dir: Path,
    *,
    sources: set[str] | None = None,
    limit: int | None = None,
) -> IngestStats:
    stats = IngestStats()
    known = set(session.scalars(select(Document.raw_sha256)))
    for rec in iter_records(corpus_dir, sources):
        if limit is not None and stats.created >= limit:
            break
        stats.seen += 1
        sha = rec.get("sha256")
        raw = rec.get("file") or rec.get("text_file")  # older SEBI orders exist only as extracted web text
        if not sha or not raw or not (corpus_dir / raw).is_file():
            stats.missing_file += 1
            log.warning("skipping %s: no file on disk", rec.get("title"))
            continue
        if sha in known:
            stats.existing += 1
            continue
        known.add(sha)
        category = rec.get("category") or ""
        session.add(
            Document(
                source_kind=SOURCE_KIND[rec["source"]],
                url=rec.get("pdf_url") or rec.get("url"),
                title=(rec.get("title") or "").strip() or "Untitled",
                doc_type=DOC_TYPE.get(category, category or None),
                published_at=date.fromisoformat(rec["date"]) if rec.get("date") else None,
                raw_sha256=sha,
                raw_path=raw,
                status="ingested",
                meta={
                    "collector": rec["source"],
                    "category": category,
                    "label": rec.get("label"),
                    "page_url": rec.get("url"),
                    "retrieved_at": rec.get("retrieved_at"),
                    "html_only": bool(rec.get("html_only")),
                },
            )
        )
        stats.created += 1
        stats.by_source[rec["source"]] = stats.by_source.get(rec["source"], 0) + 1
    session.flush()
    return stats
