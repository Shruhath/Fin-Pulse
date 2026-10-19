from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import text

from finpulse.db.models import (
    Claim,
    Document,
    Entity,
    EntityAlias,
    EvalResult,
    Event,
    Mention,
    MentionSentiment,
    Sentence,
    Summary,
)

pytestmark = pytest.mark.db

TEXT = (
    "SEBI imposed a penalty of Rs. 5 lakh on Yes Bank Limited. The noticee PAN ABCDE1234F was named. "
    "Yes Bank Limited paid promptly."
)


def _seed(db):
    yes = Entity(slug="yes-bank", canonical_name="Yes Bank Limited", nse_symbol="YESBANK", kind="bank")
    other = Entity(slug="tata-motors", canonical_name="Tata Motors Limited", nse_symbol="TATAMOTORS")
    person = Entity(slug="some-person", canonical_name="Some Person", kind="person")
    db.add_all([yes, other, person])
    db.flush()
    db.add(EntityAlias(entity_id=yes.id, alias="Yes Bank", alias_norm="yes bank", origin="nse"))
    docs = []
    for i, (day, sha) in enumerate(((date(2026, 10, 10), "1" * 64), (date(2026, 9, 20), "2" * 64))):
        doc = Document(
            source_kind="SEBI",
            title=f"Order {i} in the matter of Yes Bank Limited",
            raw_sha256=sha,
            clean_text=TEXT,
            n_words=len(TEXT.split()),
            status="analysed",
            doc_type="SEBI adjudication order",
            published_at=day,
            url=f"https://example.test/{i}",
        )
        db.add(doc)
        db.flush()
        for j, sp in enumerate(((0, 59), (60, 98), (99, len(TEXT)))):
            db.add(Sentence(doc_id=doc.id, idx=j, char_start=sp[0], char_end=sp[1], text=TEXT[sp[0] : sp[1]]))
        docs.append(doc)
    db.flush()

    sentences = {(s.doc_id, s.idx): s for s in db.query(Sentence).all()}
    first = TEXT.index("Yes Bank Limited")
    for doc, (label, pos, neg, neu, conf) in zip(
        docs, (("negative", 0.1, 0.8, 0.1, 0.8), ("positive", 0.7, 0.1, 0.2, 0.7)), strict=True
    ):
        m = Mention(
            doc_id=doc.id,
            sentence_id=sentences[(doc.id, 0)].id,
            entity_id=yes.id,
            char_start=first,
            char_end=first + len("Yes Bank Limited"),
            surface="Yes Bank Limited",
            ner_model="gazetteer-rules",
            link_method="exact",
            link_score=100.0,
        )
        db.add(m)
        db.flush()
        db.add(
            MentionSentiment(
                mention_id=m.id,
                model_version="tfidf-lr@test",
                label=label,
                p_pos=pos,
                p_neg=neg,
                p_neu=neu,
                confidence=conf,
            )
        )
    ev = Event(
        doc_id=docs[0].id,
        entity_id=yes.id,
        type="SEBI Penalty",
        trigger_start=0,
        trigger_end=59,
        arguments={"action": "penalty", "provisions": "Section 15HB of SEBI Act"},
        event_date=date(2026, 10, 10),
        amount_inr=Decimal(500000),
        extractor="rules",
    )
    db.add(ev)
    db.flush()
    db.execute(text("refresh materialized view entity_daily"))
    return yes, docs, ev


def test_empty_corpus_returns_empty_collections_not_placeholders(client):
    assert client.get("/api/status").json() == {
        "documents": 0,
        "entities": 0,
        "events": 0,
        "lastIngestAt": None,
    }
    overview = client.get("/api/overview").json()
    assert overview["market"] == overview["entities"] == overview["filings"] == overview["events"] == []
    assert overview["asOf"] is None and overview["sentimentModel"] is None
    assert client.get("/api/entities").json() == []
    assert client.get("/api/wallpaper").json() == []
    assert client.get("/api/documents/1").status_code == 404
    assert client.get("/api/entities/nobody").status_code == 404


def test_overview_is_computed_from_stored_rows(client, db):
    _seed(db)
    body = client.get("/api/overview?window=90d").json()
    assert body["asOf"] == "2026-10-10"
    assert body["sentimentModel"] == "tfidf-lr@test"
    assert body["corpus"]["documents"] == 2 and body["corpus"]["events"] == 1
    assert body["sources"] == [{"kind": "SEBI", "documents": 2}]
    assert [p["t"] for p in body["market"]] == ["2026-09-20", "2026-10-10"]
    assert body["market"][0]["mean"] == pytest.approx(0.6) and body["market"][1]["mean"] == pytest.approx(
        -0.7
    )
    (entity,) = body["entities"]
    assert entity["id"] == "yes-bank" and entity["ticker"] == "YESBANK" and entity["mentions"] == 2
    assert entity["score"] == pytest.approx((0.6 - 0.7) / 2)
    assert entity["sentiment"] == "neutral"  # the mean sits inside the neutral band
    assert [p["v"] for p in entity["series"]] == pytest.approx([0.6, -0.7])
    (event,) = body["events"]
    assert (
        event["headline"] == "SEBI penalty of ₹5 lakh on Yes Bank Limited" and event["group"] == "Regulatory"
    )
    assert body["filings"][0]["entities"] == [
        {"id": "yes-bank", "name": "Yes Bank Limited", "sentiment": "negative"}
    ]


def _score_another_day(db, entity, day, p_pos, p_neg, sha):
    doc = Document(
        source_kind="SEBI",
        title="Earlier order",
        raw_sha256=sha,
        clean_text=TEXT,
        status="analysed",
        published_at=day,
    )
    db.add(doc)
    db.flush()
    m = Mention(
        doc_id=doc.id,
        entity_id=entity.id,
        char_start=0,
        char_end=3,
        surface="SEB",
        ner_model="gazetteer-rules",
    )
    db.add(m)
    db.flush()
    db.add(
        MentionSentiment(
            mention_id=m.id,
            model_version="tfidf-lr@test",
            label="positive",
            p_pos=p_pos,
            p_neg=p_neg,
            p_neu=1 - p_pos - p_neg,
            confidence=0.9,
        )
    )
    db.flush()
    db.execute(text("refresh materialized view entity_daily"))


def test_windows_are_anchored_on_the_newest_document(client, db):
    _seed(db)
    short = client.get("/api/entities?window=7d").json()
    assert short[0]["mentions"] == 1 and short[0]["score"] == pytest.approx(-0.7)
    assert short[0]["delta"] is None  # nothing was scored in the 7 days before that window
    assert client.get("/api/entities?window=banana").status_code == 422


def test_delta_compares_with_the_window_before(client, db):
    yes, _, _ = _seed(db)
    _score_another_day(
        db, yes, date(2026, 9, 2), 0.9, 0.0, "9" * 64
    )  # inside the 30 days before the 30d window
    row = client.get("/api/entities?window=30d").json()[0]
    assert row["mentions"] == 2  # 2026-09-20 and 2026-10-10 are inside the window, 2026-09-02 is not
    assert row["score"] == pytest.approx((0.6 - 0.7) / 2)
    assert row["delta"] == pytest.approx((0.6 - 0.7) / 2 - 0.9)


def test_entity_filters_and_person_entities_are_not_companies(client, db):
    _seed(db)
    assert [e["id"] for e in client.get("/api/entities?q=yes&window=all").json()] == ["yes-bank"]
    assert client.get("/api/entities?q=tata&window=all").json() == []  # no scored mentions
    assert all(e["kind"] != "person" for e in client.get("/api/entities?window=all").json())


def test_document_detail_masks_pan_without_moving_offsets(client, db):
    _, docs, _ = _seed(db)
    body = client.get(f"/api/documents/{docs[0].id}").json()
    assert "ABCDE1234F" not in body["text"] and "XXXXXXXXXX" in body["text"]
    assert len(body["text"]) == len(TEXT)
    (span,) = body["spans"]
    assert body["text"][span["start"] : span["end"]] == span["surface"] == "Yes Bank Limited"
    assert span["entityId"] == "yes-bank" and span["sentiment"] == "negative"
    (event,) = body["events"]
    assert body["text"][event["trigger"]["start"] : event["trigger"]["end"]].startswith("SEBI imposed")
    assert event["arguments"]["amount"] == "₹5 lakh" and event["extractor"] == "rules"
    assert event["confidence"] is None and event["sentiment"] == "negative"
    assert body["summary"] is None and body["status"] == "analysed" and body["publishedAt"] == "2026-10-10"


def test_company_detail_has_aliases_mentions_and_events(client, db):
    _seed(db)
    body = client.get("/api/entities/yes-bank?window=all").json()
    assert body["aliases"] == ["Yes Bank"]
    assert len(body["events"]) == 1
    first = body["mentions"][0]
    assert first["sentence"][first["start"] : first["end"]] == "Yes Bank Limited"
    assert first["sentiment"] == "negative"
    assert body["entity"]["mentions"] == 2


def test_events_filters(client, db):
    _seed(db)
    assert len(client.get("/api/events?type=SEBI Penalty").json()) == 1
    assert client.get("/api/events?type=Stock Split").json() == []
    assert len(client.get("/api/events?entity=yes-bank&window=30d").json()) == 1
    assert client.get("/api/events?entity=tata-motors").json() == []


def test_documents_list_and_filters(client, db):
    _seed(db)
    assert len(client.get("/api/documents").json()) == 2
    assert client.get("/api/documents?source=RBI").json() == []
    assert len(client.get("/api/documents?q=order 1").json()) == 1
    assert client.get("/api/documents?status=nonsense").status_code == 422


def test_search_index_lists_only_companies_with_mentions(client, db):
    _seed(db)
    body = client.get("/api/search/index").json()
    assert body["companies"] == [{"id": "yes-bank", "name": "Yes Bank Limited", "ticker": "YESBANK"}]
    assert len(body["filings"]) == 2


def test_wallpaper_is_a_grid_of_real_daily_scores(client, db):
    _seed(db)
    grid = client.get("/api/wallpaper").json()
    assert len(grid) == 1 and len(grid[0]) == 90
    assert grid[0][-1] == pytest.approx(-0.7)  # the newest day
    assert grid[0][-1 - 20] == pytest.approx(0.6)  # 20 days earlier
    assert grid[0][0] == 0.0


def test_eval_report_comes_only_from_recorded_runs(client, db):
    empty = client.get("/api/eval").json()
    assert empty == {"generatedAt": None, "rows": [], "confusion": None, "reliability": None, "agreement": []}
    db.add(
        EvalResult(
            stage="sentiment",
            model="TF-IDF + LR",
            baseline=True,
            dataset="SEntFiN test",
            split="test",
            indian=True,
            metrics={"macroF1": 0.8, "ece": 0.03, "n": 100.0},
            git_sha="abc",
            detail={
                "labels": ["negative", "neutral", "positive"],
                "confusion": [[5, 1, 0], [0, 6, 1], [0, 1, 6]],
                "reliability": [{"confidence": 0.9, "accuracy": 0.85, "n": 20}],
            },
        )
    )
    db.flush()
    body = client.get("/api/eval").json()
    assert body["rows"][0]["metrics"]["macroF1"] == 0.8 and body["rows"][0]["indian"] is True
    assert body["confusion"]["matrix"][0] == [5, 1, 0]
    assert body["reliability"]["eceBefore"] == 0.03 and body["reliability"]["after"] is None


def test_a_stored_summary_is_returned_with_its_evidence_sentence(client, db):
    _, docs, _ = _seed(db)
    summary = Summary(scope="document", doc_id=docs[0].id, model="llama3.1:8b-instruct", prompt_version="v1")
    db.add(summary)
    db.flush()
    sentence = db.query(Sentence).filter_by(doc_id=docs[0].id, idx=0).one()
    db.add_all(
        [
            Claim(
                summary_id=summary.id,
                idx=0,
                text="SEBI fined Yes Bank.",
                verification="entailed",
                nli_entail=0.93,
                nli_contra=0.01,
                evidence_sentence_id=sentence.id,
            ),
            Claim(
                summary_id=summary.id,
                idx=1,
                text="The fine was Rs. 5 crore.",
                verification="contradicted",
                nli_entail=0.02,
                nli_contra=0.9,
            ),
        ]
    )
    db.flush()
    body = client.get(f"/api/documents/{docs[0].id}").json()["summary"]
    assert body["model"] == "llama3.1:8b-instruct" and body["scope"] == "document"
    assert [c["verification"] for c in body["claims"]] == ["entailed", "contradicted"]  # contradicted is kept
    assert body["claims"][0]["evidence"]["text"].startswith("SEBI imposed")
    assert body["claims"][1]["evidence"] is None


def test_health_and_config(client):
    health = client.get("/api/health").json()
    assert health["database"] is True and health["status"] == "ok" and health["queuedJobs"] == 0
    cfg = client.get("/api/pipeline/config").json()
    assert cfg["scoreBand"] == 0.15 and cfg["eventModel"]


def test_summaries_endpoint_lists_document_and_entity_summaries_with_subjects(client, db):
    yes, docs, _ = _seed(db)
    db.add(Summary(scope="document", doc_id=docs[0].id, model="llama", prompt_version="summary-v1"))
    db.add(
        Summary(
            scope="entity_window", entity_id=yes.id, window_end=date(2026, 10, 10), model="llama",
            prompt_version="summary-v1",
        )
    )  # fmt: skip
    db.flush()
    body = client.get("/api/summaries").json()
    assert {(b["scope"], b["subject"]) for b in body} == {
        ("document", docs[0].title),
        ("entity", "Yes Bank Limited"),
    }
    only = client.get("/api/summaries?entity=yes-bank").json()
    assert [b["entityId"] for b in only] == ["yes-bank"]
    assert client.get("/api/summaries?entity=tata-motors").json() == []


def test_events_prefer_the_llm_extractor_when_a_document_has_both(client, db):
    yes, docs, _ = _seed(db)
    db.add(
        Event(
            doc_id=docs[0].id, entity_id=yes.id, type="SEBI Penalty", trigger_start=0, trigger_end=59,
            arguments={"action": "penalty"}, event_date=date(2026, 10, 10), extractor="llm",
        )
    )  # fmt: skip
    db.flush()
    assert [e["extractor"] for e in client.get("/api/events").json()] == ["llm"]
    assert {e["extractor"] for e in client.get("/api/events?extractor=rules").json()} == {"rules"}
    assert len(client.get("/api/events?extractor=llm").json()) == 1
    assert client.get("/api/events?extractor=other").status_code == 422
    assert [e["extractor"] for e in client.get(f"/api/documents/{docs[0].id}").json()["events"]] == ["llm"]


def test_an_event_takes_the_sentiment_scored_inside_its_trigger_sentence(client, db):
    _seed(db)
    (event,) = client.get("/api/events").json()
    assert event["sentiment"] == "negative"  # the mention inside the trigger sentence was scored negative


def test_search_finds_companies_by_fuzzy_name_and_documents_by_text(client, db):
    _seed(db)
    found = client.get("/api/search?q=yes bank").json()
    assert found["companies"][0]["id"] == "yes-bank"
    assert found["filings"] and "<mark>" in found["filings"][0]["snippet"]
    assert len({f["documentId"] for f in found["filings"]}) == len(found["filings"])  # one hit per document
    assert client.get("/api/search?q=penalties").json()["filings"]  # stemming: penalties matches penalty
    assert client.get("/api/search?q=zzzzqqq").json() == {"query": "zzzzqqq", "companies": [], "filings": []}
    assert client.get("/api/search?q=a").status_code == 422
