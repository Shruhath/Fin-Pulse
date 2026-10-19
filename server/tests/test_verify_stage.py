import numpy as np
import pytest
from sqlalchemy import select

from finpulse.db.models import Claim, Document, Entity, Mention, Sentence, Summary
from finpulse.pipeline.embed import embed_pending
from finpulse.pipeline.verify import decide, verify_pending
from finpulse.verify.retrieval import candidate_sentences, dense_ranking
from tests.fakes import FakeEncoder, FakeJudge

pytestmark = pytest.mark.db

SENTENCES = [
    "SEBI imposed a penalty of Rs 400000 on Raga Securities for violating the broker code.",
    "The hearing was held at the SEBI office in Mumbai on Monday morning.",
    "Raga Securities is a registered stock broker with many retail clients.",
    "The matter concerns delayed reporting of client funds to the exchange.",
]


def _doc(db, sha="a" * 64):
    doc = Document(
        source_kind="SEBI", title="Order", raw_sha256=sha, clean_text=" ".join(SENTENCES), status="analysed"
    )
    db.add(doc)
    db.flush()
    sents = []
    pos = 0
    for i, t in enumerate(SENTENCES):
        s = Sentence(doc_id=doc.id, idx=i, char_start=pos, char_end=pos + len(t), text=t)
        db.add(s)
        sents.append(s)
        pos += len(t) + 1
    db.flush()
    return doc, sents


def _summary(db, doc, claims, **kw):
    summary = Summary(scope="document", doc_id=doc.id, model="llama", prompt_version="summary-v1", **kw)
    db.add(summary)
    db.flush()
    rows = [Claim(summary_id=summary.id, idx=i, text=t, cited=c) for i, (t, c) in enumerate(claims)]
    db.add_all(rows)
    db.flush()
    return summary, rows


def test_decision_thresholds():
    assert decide(0.9, 0.05) == "entailed"
    assert decide(0.69, 0.1) == "unverified"
    assert decide(0.1, 0.8) == "contradicted"
    assert decide(0.75, 0.9) == "contradicted"  # contradiction outweighs a weaker entailment


def test_embedding_stage_fills_vectors_once_and_checks_the_dimension(db):
    _, sents = _doc(db)
    stats = embed_pending(db, FakeEncoder())
    assert stats.sentences == 4
    db.refresh(sents[0])
    vec = np.asarray(sents[0].embedding)
    assert vec.shape == (1024,) and np.linalg.norm(vec) == pytest.approx(1.0, abs=1e-5)
    assert embed_pending(db, FakeEncoder()).sentences == 0

    class Small(FakeEncoder):
        dim = 32

    with pytest.raises(ValueError, match="1024"):
        embed_pending(db, Small())


def test_dense_ranking_orders_by_cosine_similarity(db):
    _, sents = _doc(db)
    embed_pending(db, FakeEncoder())
    query = FakeEncoder().encode(["penalty imposed on Raga Securities"])[0]
    ranked = dense_ranking(db, query, [s.id for s in sents])
    assert ranked[0] == sents[0].id


def test_a_supported_claim_is_entailed_with_its_evidence_and_rank(db):
    doc, sents = _doc(db)
    embed_pending(db, FakeEncoder())
    _, (claim,) = _summary(db, doc, [("SEBI imposed a penalty of Rs 400000 on Raga Securities.", [])])
    stats = verify_pending(db, FakeJudge(), FakeEncoder())
    assert (stats.claims, stats.entailed) == (1, 1)
    assert claim.verification == "entailed" and claim.evidence_sentence_id == sents[0].id
    assert claim.nli_entail == pytest.approx(0.95) and claim.retrieval_rank == 1


def test_a_claim_with_the_wrong_amount_is_contradicted_and_kept(db):
    doc, sents = _doc(db)
    _, (claim,) = _summary(db, doc, [("SEBI imposed a penalty of Rs 5000000 on Raga Securities.", [])])
    verify_pending(db, FakeJudge())  # BM25 only: no embeddings were made
    assert claim.verification == "contradicted" and claim.nli_contra == pytest.approx(0.90)
    assert claim.evidence_sentence_id == sents[0].id
    assert db.scalar(select(Claim).where(Claim.id == claim.id)) is not None


def test_an_unrelated_claim_stays_unverified_and_cited_sentences_are_still_judged(db):
    doc, sents = _doc(db)
    _, (a, b) = _summary(
        db,
        doc,
        [
            ("The company won an export award in Singapore.", []),
            ("It trades for retail clients.", [sents[2].id]),
        ],
    )
    stats = verify_pending(db, FakeJudge())
    assert a.verification == "unverified" and b.verification in {"entailed", "unverified"}
    assert b.evidence_sentence_id is not None  # judged against the cited sentence even if retrieval missed it
    assert stats.claims == 2 and stats.entailed + stats.contradicted + stats.unverified == 2


def test_only_unjudged_claims_are_processed_again_unless_redo(db):
    doc, _ = _doc(db)
    _summary(db, doc, [("SEBI imposed a penalty of Rs 400000 on Raga Securities.", [])])
    assert verify_pending(db, FakeJudge()).claims == 1
    assert verify_pending(db, FakeJudge()).claims == 0
    assert verify_pending(db, FakeJudge(), redo=True).claims == 1


def test_entity_summaries_search_the_documents_that_mention_the_company(db):
    doc, sents = _doc(db)
    other = Document(
        source_kind="SEBI", title="Other", raw_sha256="b" * 64, clean_text="x", status="analysed"
    )
    db.add(other)
    db.flush()
    db.add(Sentence(doc_id=other.id, idx=0, char_start=0, char_end=1, text="Unrelated sentence elsewhere."))
    ent = Entity(slug="raga", canonical_name="Raga")
    db.add(ent)
    db.flush()
    db.add(
        Mention(
            doc_id=doc.id,
            sentence_id=sents[0].id,
            entity_id=ent.id,
            char_start=0,
            char_end=4,
            surface="SEBI",
            ner_model="t",
        )
    )
    summary = Summary(scope="entity_window", entity_id=ent.id, model="m", prompt_version="v1")
    db.add(summary)
    db.flush()
    texts = {t for _, t in candidate_sentences(db, summary)}
    assert texts == set(SENTENCES)
