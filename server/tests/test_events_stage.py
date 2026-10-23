from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from finpulse.db.models import Document, Entity, Event, Sentence
from finpulse.pipeline.events import extract_pending
from finpulse.pipeline.link import link_pending
from finpulse.preprocess.sentences import split_sentences

pytestmark = pytest.mark.db

ORDER = (
    "In the matter of Raga Securities and Finance Private Limited.\n\n"
    "20. In exercise of the powers conferred under section 15 I of the SEBI Act, I hereby imposed a penalty "
    "of Rs. 4,00,000/- on the Noticee viz. Raga Securities and Finance Private Limited under section 15HB "
    "of SEBI Act."
)


def _doc(db, title, text, doc_type, kind="SEBI", sha="a" * 64):
    doc = Document(
        source_kind=kind,
        title=title,
        raw_sha256=sha,
        clean_text=text,
        status="parsed",
        doc_type=doc_type,
        published_at=date(2024, 5, 2),
    )
    db.add(doc)
    db.flush()
    for i, s in enumerate(split_sentences(text)):
        db.add(Sentence(doc_id=doc.id, idx=i, char_start=s.start, char_end=s.end, text=s.slice(text)))
    db.flush()
    return doc


def test_penalty_event_is_stored_against_the_title_party(db):
    doc = _doc(
        db,
        "Adjudication Order in the matter of Raga Securities and Finance Private Limited",
        ORDER,
        "SEBI adjudication order",
    )
    link_pending(db)
    stats = extract_pending(db)
    assert (stats.documents, stats.events, stats.without_entity, stats.invalid) == (1, 1, 0, 0)

    ev = db.scalar(select(Event).where(Event.doc_id == doc.id))
    raga = db.scalar(select(Entity).where(Entity.canonical_name.like("Raga Securities%")))
    assert ev.entity_id == raga.id
    assert ev.type == "SEBI Penalty" and ev.amount_inr == Decimal(400000)
    assert ev.extractor == "rules" and ev.confidence is None and ev.schema_valid
    assert doc.clean_text[ev.trigger_start : ev.trigger_end].startswith("20. In exercise")
    assert ev.event_date == date(2024, 5, 2)


def test_rerunning_replaces_instead_of_duplicating(db):
    doc = _doc(
        db,
        "Order in the matter of Raga Securities and Finance Private Limited",
        ORDER,
        "SEBI adjudication order",
        sha="b" * 64,
    )
    link_pending(db)
    extract_pending(db)
    extract_pending(db)
    assert len(list(db.scalars(select(Event).where(Event.doc_id == doc.id)))) == 1


def test_documents_without_an_operative_sentence_get_no_event(db):
    _doc(
        db,
        "Order in the matter of Someone Limited",
        "The matter was heard and adjourned.",
        "SEBI adjudication order",
        sha="c" * 64,
    )
    link_pending(db)
    assert extract_pending(db).events == 0
