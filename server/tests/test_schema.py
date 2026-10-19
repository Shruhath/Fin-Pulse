from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from finpulse.db.models import (
    Annotation,
    Document,
    Entity,
    Mention,
    MentionSentiment,
    Sentence,
    Source,
)

pytestmark = pytest.mark.db


def _doc(db, sha="a" * 64, **kw) -> Document:
    doc = Document(
        source_kind="SEBI", title="Order", raw_sha256=sha, clean_text="Yes Bank was penalised.", **kw
    )
    db.add(doc)
    db.flush()
    return doc


def test_all_source_kinds_are_seeded(db):
    kinds = {s.kind for s in db.scalars(select(Source))}
    assert kinds == {"BSE", "NSE", "SEBI", "RBI", "NCLT", "NEWS"}


def test_documents_are_idempotent_on_raw_hash(db):
    _doc(db, sha="b" * 64)
    with pytest.raises(IntegrityError), db.begin_nested():
        _doc(db, sha="b" * 64)


def test_document_rejects_an_unknown_status(db):
    with pytest.raises(IntegrityError), db.begin_nested():
        _doc(db, sha="c" * 64, status="done")


def test_sentence_text_search_vector_is_generated(db):
    doc = _doc(db, sha="d" * 64)
    db.add(Sentence(doc_id=doc.id, idx=0, char_start=0, char_end=23, text="Yes Bank was penalised."))
    db.flush()
    hits = db.scalar(
        text("select count(*) from sentences where tsv @@ plainto_tsquery('english', 'penalised bank')")
    )
    assert hits == 1


def test_gold_and_silver_are_the_only_label_sources(db):
    db.add(Annotation(task="sentiment", payload={}, label_source="gold", annotator="a"))
    db.flush()
    with pytest.raises(IntegrityError), db.begin_nested():
        db.add(Annotation(task="sentiment", payload={}, label_source="maybe", annotator="a"))
        db.flush()


def test_mention_span_must_be_non_empty(db):
    doc = _doc(db, sha="e" * 64)
    with pytest.raises(IntegrityError), db.begin_nested():
        db.add(Mention(doc_id=doc.id, char_start=5, char_end=5, surface="", ner_model="rules"))
        db.flush()


def test_entity_daily_aggregates_signed_scores(db):
    ent = Entity(slug="yes-bank", canonical_name="Yes Bank Limited", kind="bank")
    doc = _doc(db, sha="f" * 64, published_at=date(2026, 3, 2))
    db.add(ent)
    db.flush()
    for label, pos, neg, neu in (("positive", 0.8, 0.1, 0.1), ("negative", 0.1, 0.7, 0.2)):
        m = Mention(
            doc_id=doc.id, entity_id=ent.id, char_start=0, char_end=8, surface="Yes Bank", ner_model="rules"
        )
        db.add(m)
        db.flush()
        db.add(
            MentionSentiment(
                mention_id=m.id,
                model_version="t",
                label=label,
                p_pos=pos,
                p_neg=neg,
                p_neu=neu,
                confidence=0.9,
            )
        )
    db.flush()
    db.execute(text("refresh materialized view entity_daily"))
    row = db.execute(
        text("select score_mean, mentions from entity_daily where entity_id = :e"), {"e": ent.id}
    ).one()
    assert row.mentions == 2
    assert row.score_mean == pytest.approx(((0.8 - 0.1) + (0.1 - 0.7)) / 2)


def test_models_and_migrations_agree(migrated_db):
    """`alembic check` finds no difference between the ORM models and the migrated database."""
    from alembic import command
    from alembic.config import Config

    server_dir = Path(__file__).resolve().parents[1]
    cfg = Config(str(server_dir / "alembic.ini"))
    cfg.set_main_option("script_location", str(server_dir / "alembic"))
    command.check(cfg)
