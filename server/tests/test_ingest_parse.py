import json

import pymupdf
import pytest
from sqlalchemy import func, select

from finpulse.core.settings import get_settings
from finpulse.db.models import Document, Run, Sentence
from finpulse.ingest.corpus import ingest_corpus
from finpulse.pipeline.parse import parse_pending

pytestmark = pytest.mark.db

BODY = (
    "The Adjudicating Officer imposed a penalty of Rs. 25,00,000 on Yes Bank Limited under "
    "Section 15HA of the SEBI Act. The order is final."
)


def _make_corpus(root):
    (root / "sebi_orders" / "pdf").mkdir(parents=True)
    (root / "sebi_orders" / "text").mkdir()
    pdf = root / "sebi_orders" / "pdf" / "a.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_textbox(pymupdf.Rect(60, 60, 540, 400), BODY, fontsize=12)
    doc.save(pdf)
    doc.close()
    scan = pymupdf.open()
    src = pymupdf.open()
    sp = src.new_page()
    sp.insert_textbox(pymupdf.Rect(60, 60, 540, 400), BODY, fontsize=14)
    img = scan.new_page(width=sp.rect.width, height=sp.rect.height)
    img.insert_image(img.rect, stream=sp.get_pixmap(dpi=200).tobytes("png"))
    scan.save(root / "sebi_orders" / "pdf" / "b.pdf")
    html_only = root / "sebi_orders" / "text" / "old.txt"
    html_only.write_text("Order against M/s Kamlesh Jain & Co. The noticee is directed to pay Rs. 5 lakh.")

    def rec(**kw):
        return {"source": "sebi_orders", "category": "ao", "text_layer": True, **kw}

    records = [
        rec(date="2024-05-02", title="Order in the matter of Yes Bank", url="https://example.test/a",
            pdf_url="https://example.test/a.pdf", file="sebi_orders/pdf/a.pdf", sha256="1" * 64),
        rec(date="2023-01-09", title="Scanned order", category="wtm", url="https://example.test/b",
            pdf_url="https://example.test/b.pdf", file="sebi_orders/pdf/b.pdf", sha256="2" * 64,
            text_layer=False),
        rec(date="2004-11-02", title="Order against Kamlesh Jain", url="https://example.test/c", pdf_url=None,
            file=None, html_only=True, text_file="sebi_orders/text/old.txt", sha256="3" * 64),
        rec(date="2020-01-01", title="Dead link", url="https://example.test/d",
            file="sebi_orders/pdf/missing.pdf", sha256="4" * 64),
    ]  # fmt: skip
    (root / "sebi_orders" / "index.jsonl").write_text("\n".join(json.dumps(r) for r in records))


@pytest.fixture
def corpus(tmp_path, monkeypatch):
    _make_corpus(tmp_path)
    monkeypatch.setattr(get_settings(), "corpus_dir", tmp_path)
    return tmp_path


def test_ingest_is_idempotent_and_reports_missing_files(db, corpus):
    first = ingest_corpus(db, corpus)
    assert (first.seen, first.created, first.missing_file) == (4, 3, 1)
    second = ingest_corpus(db, corpus)
    assert (second.created, second.existing) == (0, 3)
    assert db.scalar(select(func.count()).select_from(Document)) == 3
    wtm = db.scalar(select(Document).where(Document.title == "Scanned order"))
    assert wtm.source_kind == "SEBI"
    assert wtm.doc_type == "SEBI whole-time member order"
    assert str(wtm.published_at) == "2023-01-09"
    assert wtm.status == "ingested"


def test_parse_fills_clean_text_sentences_and_ocr_flag(db, corpus):
    ingest_corpus(db, corpus)
    stats = parse_pending(db, workers=2)
    assert (stats.parsed, stats.failed, stats.ocr_documents) == (3, 0, 1)

    text_doc = db.scalar(select(Document).where(Document.title == "Order in the matter of Yes Bank"))
    assert text_doc.status == "parsed" and not text_doc.ocr_used
    assert "Yes Bank Limited" in text_doc.clean_text
    sents = list(db.scalars(select(Sentence).where(Sentence.doc_id == text_doc.id).order_by(Sentence.idx)))
    assert [s.text for s in sents] == [
        "The Adjudicating Officer imposed a penalty of Rs. 25,00,000 on Yes Bank Limited under "
        "Section 15HA of the SEBI Act.",
        "The order is final.",
    ]
    # the stored offsets slice back to the sentence text
    assert all(text_doc.clean_text[s.char_start : s.char_end] == s.text for s in sents)

    scan = db.scalar(select(Document).where(Document.title == "Scanned order"))
    assert scan.ocr_used and scan.meta["ocr_pages"] == 1
    assert "Yes Bank Limited" in " ".join(scan.clean_text.split())

    run = db.scalar(select(Run).where(Run.stage == "parse"))
    assert run.status == "done" and run.latency_ms is not None


def test_parse_marks_unreadable_files_failed(db, corpus):
    ingest_corpus(db, corpus)
    (corpus / "sebi_orders" / "pdf" / "a.pdf").write_bytes(b"not a pdf")
    stats = parse_pending(db, workers=1, ocr=False)
    assert stats.failed == 1
    bad = db.scalar(select(Document).where(Document.title == "Order in the matter of Yes Bank"))
    assert bad.status == "failed" and "error" in bad.meta
    assert parse_pending(db, workers=1, ocr=False).parsed == 0  # failed docs are not retried silently
