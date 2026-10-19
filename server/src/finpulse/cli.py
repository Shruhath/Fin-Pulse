"""`finpulse` command line: run the pipeline stages and serve the API."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable

from sqlalchemy import func, select, text

from finpulse.core.logging import configure_logging
from finpulse.core.settings import get_settings
from finpulse.db.models import Document, Entity, Event, Mention, Sentence
from finpulse.db.session import session_scope


def _status(_: argparse.Namespace) -> int:
    with session_scope() as s:
        s.execute(text("select 1"))
        counts = {
            "documents": s.scalar(select(func.count()).select_from(Document)),
            "parsed": s.scalar(select(func.count()).select_from(Document).where(Document.status == "parsed")),
            "failed": s.scalar(select(func.count()).select_from(Document).where(Document.status == "failed")),
            "ocr": s.scalar(select(func.count()).select_from(Document).where(Document.ocr_used)),
            "sentences": s.scalar(select(func.count()).select_from(Sentence)),
            "entities": s.scalar(select(func.count()).select_from(Entity)),
            "mentions": s.scalar(select(func.count()).select_from(Mention)),
            "events": s.scalar(select(func.count()).select_from(Event)),
        }
    print("  ".join(f"{k}={v}" for k, v in counts.items()))
    return 0


def _gazetteer_seed(_: argparse.Namespace) -> int:
    from finpulse.entities.gazetteer import seed_gazetteer

    with session_scope() as s:
        st = seed_gazetteer(s, get_settings().benchmark_dir)
    print(
        f"entities +{st.entities} (nse {st.from_nse}, sentfin {st.from_sentfin}, "
        f"{st.skipped} sentfin rows skipped as non-companies), aliases +{st.aliases}"
    )
    return 0


def _ingest_corpus(a: argparse.Namespace) -> int:
    from finpulse.ingest.corpus import ingest_corpus

    with session_scope() as s:
        st = ingest_corpus(s, get_settings().corpus_dir, sources=set(a.source) or None, limit=a.limit)
    print(f"seen {st.seen}, new {st.created}, already stored {st.existing}, missing file {st.missing_file}")
    return 0


def _parse(a: argparse.Namespace) -> int:
    from finpulse.pipeline.parse import parse_pending

    def progress(done: int, total: int, doc: Document) -> None:
        flag = " [OCR]" if doc.ocr_used else ""
        print(f"[{done}/{total}] {doc.n_pages or 0}p {doc.n_words}w{flag}  {doc.title[:70]}", flush=True)

    with session_scope() as s:
        st = parse_pending(
            s, workers=a.workers, limit=a.limit, ocr=not a.no_ocr, redo=a.redo, progress=progress
        )
    print(f"parsed {st.parsed}, failed {st.failed}, scanned documents read with OCR {st.ocr_documents}")
    return 0 if st.failed == 0 else 1


def _link(a: argparse.Namespace) -> int:
    from finpulse.pipeline.link import link_pending

    with session_scope() as s:
        st = link_pending(s, limit=a.limit, relink=a.relink)
    print(
        f"documents {st.documents}, mentions {st.mentions} ({st.unresolved} unresolved), "
        f"new entities {st.created_entities}"
    )
    return 0


def _events(a: argparse.Namespace) -> int:
    from finpulse.pipeline.events import extract_pending

    with session_scope() as s:
        st = extract_pending(s, limit=a.limit)
    print(
        f"documents {st.documents}, events {st.events} ({st.without_entity} without an entity, "
        f"{st.invalid} failing their schema)"
    )
    return 0


def _dedup(a: argparse.Namespace) -> int:
    from finpulse.pipeline.dedup import dedup_documents

    with session_scope() as s:
        total, dupes = dedup_documents(s, a.threshold)
    print(f"{total} documents, {dupes} near-duplicates of an earlier one")
    return 0


def _serve(a: argparse.Namespace) -> int:
    import uvicorn

    uvicorn.run("finpulse.api.app:app", host=a.host, port=a.port, reload=a.reload)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="finpulse", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name: str, fn: Callable[[argparse.Namespace], int], help: str) -> argparse.ArgumentParser:
        sp = sub.add_parser(name, help=help)
        sp.set_defaults(fn=fn)
        return sp

    add("status", _status, "database counts")
    g = add(
        "gazetteer", _gazetteer_seed, "seed entities from the NSE master and SEntFiN (alias: gazetteer seed)"
    )
    g.add_argument("action", nargs="?", default="seed", choices=["seed"])

    ing = add("ingest", _ingest_corpus, "load the layer 2 corpus into the database")
    ing.add_argument("what", nargs="?", default="corpus", choices=["corpus"])
    ing.add_argument("--source", action="append", default=[], help="sebi_orders or ibbi_nclt (repeatable)")
    ing.add_argument("--limit", type=int)

    ps = add("parse", _parse, "parse ingested documents (OCR for scans)")
    ps.add_argument("--workers", type=int, default=4)
    ps.add_argument("--limit", type=int)
    ps.add_argument("--no-ocr", action="store_true")
    ps.add_argument(
        "--redo", action="store_true", help="parse documents again, replacing their text and sentences"
    )

    ln = add("link", _link, "find and link entity mentions")
    ln.add_argument("--limit", type=int)
    ln.add_argument("--relink", action="store_true", help="redo documents that already have mentions")

    ev = add("events", _events, "extract events with the rule baseline")
    ev.add_argument("--limit", type=int)

    dd = add("dedup", _dedup, "cluster near-duplicate documents")
    dd.add_argument("--threshold", type=float, default=0.85)

    sv = add("serve", _serve, "run the API")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8000)
    sv.add_argument("--reload", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    args = build_parser().parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
