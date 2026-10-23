import pytest
from sqlalchemy import select

from finpulse.db.models import Document, Entity, EntityAlias, Mention, Sentence
from finpulse.pipeline.link import link_pending
from finpulse.preprocess.sentences import split_sentences

pytestmark = pytest.mark.db

TEXT = (
    "In the matter of Selene Estate Limited.\n\n"
    "The Adjudicating Officer found that Selene Estate Limited and its director traded in the scrip of "
    "Yes Bank Limited. Selene Estate Limited paid Rs. 5 lakh. Tata was also mentioned."
)


def _doc(db, title, text=TEXT, sha="a" * 64):
    doc = Document(
        source_kind="SEBI", title=title, raw_sha256=sha, clean_text=text, status="parsed", doc_type="order"
    )
    db.add(doc)
    db.flush()
    for i, s in enumerate(split_sentences(text)):
        db.add(Sentence(doc_id=doc.id, idx=i, char_start=s.start, char_end=s.end, text=s.slice(text)))
    db.flush()
    return doc


def _gazetteer(db):
    yes = Entity(slug="yes-bank", canonical_name="Yes Bank Limited", nse_symbol="YESBANK", kind="bank")
    tata_a = Entity(slug="tata-motors", canonical_name="Tata Motors Limited", kind="company")
    tata_b = Entity(slug="tata-power", canonical_name="Tata Power Limited", kind="company")
    db.add_all([yes, tata_a, tata_b])
    db.flush()
    db.add_all(
        [
            EntityAlias(entity_id=yes.id, alias="Yes Bank Limited", alias_norm="yes bank", origin="nse"),
            EntityAlias(entity_id=tata_a.id, alias="Tata", alias_norm="tata", origin="sentfin"),
            EntityAlias(entity_id=tata_b.id, alias="Tata", alias_norm="tata", origin="sentfin"),
        ]
    )
    db.flush()
    return yes


def test_title_subject_and_gazetteer_mentions_are_exact_spans(db):
    yes = _gazetteer(db)
    doc = _doc(db, "Adjudication Order in the matter of Selene Estate Limited")
    stats = link_pending(db)
    assert (stats.documents, stats.created_entities) == (1, 1)

    selene = db.scalar(select(Entity).where(Entity.canonical_name == "Selene Estate Limited"))
    assert selene is not None and selene.kind == "company"

    mentions = list(db.scalars(select(Mention).where(Mention.doc_id == doc.id).order_by(Mention.char_start)))
    assert all(doc.clean_text[m.char_start : m.char_end] == m.surface for m in mentions)
    by_entity = {}
    for m in mentions:
        by_entity.setdefault(m.entity_id, []).append(m)
    assert len(by_entity[selene.id]) == 3  # the title line plus two body mentions
    assert {m.ner_model for m in by_entity[selene.id]} == {"title-subject"}
    assert [m.ner_model for m in by_entity[yes.id]] == ["gazetteer-rules"]
    assert by_entity[yes.id][0].link_method == "exact"
    assert all(m.sentence_id is not None for m in mentions)


def test_an_alias_shared_by_two_entities_is_ambiguous_not_guessed(db):
    _gazetteer(db)
    doc = _doc(db, "Order in the matter of Selene Estate Limited", sha="b" * 64)
    link_pending(db)
    tata = db.scalar(select(Mention).where(Mention.doc_id == doc.id, Mention.surface == "Tata"))
    assert tata.entity_id is None and tata.link_method == "ambiguous"


def test_linking_is_idempotent_and_relink_replaces(db):
    _gazetteer(db)
    doc = _doc(db, "Order in the matter of Selene Estate Limited", sha="c" * 64)
    link_pending(db)
    n = len(list(db.scalars(select(Mention).where(Mention.doc_id == doc.id))))
    assert link_pending(db).documents == 0  # nothing pending
    link_pending(db, relink=True)
    assert len(list(db.scalars(select(Mention).where(Mention.doc_id == doc.id)))) == n
    assert len(list(db.scalars(select(Entity).where(Entity.canonical_name == "Selene Estate Limited")))) == 1
