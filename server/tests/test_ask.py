import json
from datetime import date

import pytest
from sqlalchemy import select

from finpulse.db.models import Document, Entity, EntityAlias, Event, Job, Mention, Sentence
from finpulse.entities.matcher import AliasMatcher
from finpulse.llm.client import LlmError, Reply
from finpulse.pipeline.ask import Runtime, answer_question, run_ask
from finpulse.pipeline.jobs import claim_next, enqueue, finish, new_stages
from finpulse.preprocess.sentences import split_sentences
from finpulse.qa.answer import answer, build_prompt, parse_answer
from finpulse.qa.question import parse_question
from finpulse.qa.retrieve import CorpusIndex, documents_for, retrieve
from finpulse.verify.bm25 import BM25

from .fakes import FakeEncoder, FakeJudge

pytestmark = pytest.mark.db

RAGA = (
    "SEBI imposed a penalty of Rs. 4,00,000 on Raga Securities and Finance Private Limited. "
    "The penalty was imposed under section 15HB of the SEBI Act. "
    "Raga Securities traded on behalf of clients over several years."
)
VENUS = (
    "The NCLT admitted Venus Textiles Limited into insolvency resolution. "
    "An interim resolution professional was appointed for Venus Textiles Limited."
)
PASTED = "Quasar zebra penalty of Rs. 9,99,999 on Raga Securities was pasted in by a visitor."


def _doc(db, *, title, text, source, sha, day, submission=False, entity=None):
    doc = Document(
        source_kind=source, title=title, raw_sha256=sha, clean_text=text, status="analysed",
        published_at=day, is_submission=submission,
    )  # fmt: skip
    db.add(doc)
    db.flush()
    encoder = FakeEncoder()
    sentences = []
    for i, span in enumerate(split_sentences(text)):
        sentence = Sentence(
            doc_id=doc.id, idx=i, char_start=span.start, char_end=span.end, text=span.slice(text),
            embedding=encoder.encode([span.slice(text)])[0].tolist(),
        )  # fmt: skip
        db.add(sentence)
        sentences.append(sentence)
    db.flush()
    if entity is not None:
        for sentence in sentences:
            db.add(
                Mention(
                    doc_id=doc.id, sentence_id=sentence.id, entity_id=entity.id,
                    char_start=sentence.char_start, char_end=sentence.char_start + 4,
                    surface=text[sentence.char_start : sentence.char_start + 4], ner_model="t",
                )
            )  # fmt: skip
    db.flush()
    return doc, sentences


def _seed(db):
    raga = Entity(slug="raga", canonical_name="Raga Securities and Finance Private Limited")
    venus = Entity(slug="venus", canonical_name="Venus Textiles Limited")
    absent = Entity(slug="absent", canonical_name="Zenith Pharma Limited")
    db.add_all([raga, venus, absent])
    db.flush()
    for entity, alias, norm in (
        (raga, "Raga Securities", "raga securities"),
        (venus, "Venus Textiles", "venus textiles"),
        (absent, "Zenith Pharma", "zenith pharma"),
    ):
        db.add(EntityAlias(entity_id=entity.id, alias=alias, alias_norm=norm, origin="t"))
    db.flush()
    a, a_sents = _doc(db, title="Order in the matter of Raga", text=RAGA, source="SEBI", sha="a" * 64,
                      day=date(2026, 10, 1), entity=raga)  # fmt: skip
    b, b_sents = _doc(db, title="Venus Textiles Limited admitted", text=VENUS, source="NCLT", sha="b" * 64,
                      day=date(2026, 10, 5), entity=venus)  # fmt: skip
    c, _ = _doc(db, title="Pasted order", text=PASTED, source="SEBI", sha="c" * 64,
                day=date(2026, 11, 1), submission=True, entity=raga)  # fmt: skip
    return raga, venus, absent, (a, a_sents), (b, b_sents), c


class AnswerLlm:
    """Cites the first evidence sentence, or declines when told the question is unanswerable."""

    def __init__(self, decline=False, bad_first=False):
        self.decline, self.bad_first, self.calls = decline, bad_first, 0

    def chat(self, model, system, user, *, schema=None, num_predict=1024):
        self.calls += 1
        if self.bad_first and self.calls == 1:
            return Reply("not json", model, 10, 1, 1.0)
        if self.decline:
            return Reply(json.dumps({"answerable": False, "claims": []}), model, 10, 1, 1.0)
        first = int(user.split("[S")[1].split("]")[0])
        body = {
            "answerable": True,
            "claims": [
                {"text": "SEBI imposed a penalty of Rs. 4,00,000 on Raga.", "sources": [first, 99999999]}
            ],
        }
        return Reply(json.dumps(body), model, 10, 1, 1.0)


def _runtime(llm=None, judge=None, encoder=None):
    return Runtime(llm, "llama-test", encoder if encoder is not None else FakeEncoder(), judge)


# ------------------------------------------------------------------ question, bm25


def test_a_question_names_companies_and_publishers():
    m = AliasMatcher()
    m.add("Raga Securities", 1)
    m.add("Venus Textiles", 2)
    parsed = parse_question("What penalty did SEBI impose on Raga Securities?", m)
    assert parsed.entity_ids == (1,) and parsed.sources == ("SEBI",)
    lower = parse_question("why did the nclt admit venus textiles", m)
    assert lower.entity_ids == (2,) and lower.sources == ("NCLT",)
    assert parse_question("What is the weather", m).entity_ids == ()


def test_a_lower_case_single_word_company_is_found_but_everyday_words_are_not():
    m = AliasMatcher()
    m.add("Wipro", 7)
    m.add("Action", 8)
    assert parse_question("what is the share price target for wipro", m).entity_ids == (7,)
    assert parse_question("what action did sebi take", m).entity_ids == ()


def test_an_ambiguous_alias_names_no_company():
    m = AliasMatcher()
    m.add("Tata Steel", 1)
    m.add("Tata Steel", 2)
    assert parse_question("Tell me about Tata Steel", m).entity_ids == ()


def test_bm25_can_be_restricted_to_some_documents():
    bm = BM25(["penalty on raga", "penalty on venus", "dividend declared"])
    assert bm.rank("penalty", 5) == [0, 1]
    assert bm.rank("penalty", 5, allowed={1, 2}) == [1]


# ------------------------------------------------------------------ retrieval


def test_retrieval_searches_the_corpus_and_never_a_submission(db):
    _, _, _, (a, _), (b, _), pasted = _seed(db)
    index = CorpusIndex(db)
    query = "Quasar zebra penalty"
    hits = retrieve(db, index, query, vector=FakeEncoder().encode([query])[0], doc_filter=None)
    assert pasted.id not in {p.doc_id for p in hits}
    assert hits and all(p.doc_id in {a.id, b.id} for p in hits)


def test_naming_a_company_limits_the_search_to_documents_that_mention_it(db):
    raga, _, absent, (a, _), (b, _), _ = _seed(db)
    index = CorpusIndex(db)
    only_raga = documents_for(db, (raga.id,), ())
    assert only_raga == {a.id}
    hits = retrieve(db, index, "insolvency resolution professional", vector=None, doc_filter=only_raga)
    assert all(p.doc_id == a.id for p in hits)  # the Venus sentences are out of reach
    assert documents_for(db, (absent.id,), ()) == set()
    assert retrieve(db, index, "anything at all", vector=None, doc_filter=set()) == []
    assert documents_for(db, (), ("NCLT",)) == {b.id}


def test_the_same_wording_in_two_documents_is_listed_once(db):
    _seed(db)
    twin, _ = _doc(
        db, title="Copy of the order", text=RAGA, source="SEBI", sha="d" * 64, day=date(2026, 10, 2)
    )
    index = CorpusIndex(db)
    hits = retrieve(db, index, "penalty of Rs. 4,00,000 on Raga Securities", vector=None, doc_filter=None)
    texts = [p.text for p in hits]
    assert len(texts) == len(set(texts)) and twin.id is not None


def test_the_index_notices_a_changed_corpus(db):
    _seed(db)
    index = CorpusIndex(db)
    assert index.is_current(db)
    fresh = "A fresh sentence about nothing in particular."
    _doc(db, title="New order", text=fresh, source="RBI", sha="e" * 64, day=date(2026, 10, 9))
    assert not index.is_current(db)


# ------------------------------------------------------------------ answers


def test_parse_answer_keeps_only_cited_sentences_that_were_shown():
    ok, claims, dropped = parse_answer(
        {"answerable": True, "claims": [{"text": "A.", "sources": [1, 9]}]}, {1}
    )
    assert ok and claims[0].sources == [1] and dropped == 1
    assert parse_answer({"answerable": False, "claims": []}, {1}) == (False, [], 0)
    # a claim that only says the evidence is silent is a refusal, not an answer
    silent = {
        "answerable": True,
        "claims": [{"text": "Wipro's price target is not specified in the evidence.", "sources": [1]}],
    }
    assert parse_answer(silent, {1}) == (False, [], 0)
    with pytest.raises(LlmError):
        parse_answer({"answerable": True, "claims": []}, {1})
    with pytest.raises(LlmError):
        parse_answer([], {1})


def test_a_bad_reply_is_retried_with_the_reason(db):
    _seed(db)
    index = CorpusIndex(db)
    passages = retrieve(db, index, "penalty Raga", vector=None, doc_filter=None)
    llm = AnswerLlm(bad_first=True)
    result = answer(llm, "m", "What penalty?", passages)
    assert result.attempts == 2 and result.answerable and result.claims
    prompt = build_prompt("What penalty?", passages)
    assert prompt.count("[S") == len(passages) and "Order in the matter of Raga" in prompt
    assert "2026" not in prompt  # publication dates are not offered as event dates


def test_an_answer_is_drafted_then_checked_claim_by_claim(db):
    _, _, _, (a, _), _, _ = _seed(db)
    stages = []
    out = answer_question(
        db, "What penalty did SEBI impose on Raga Securities?", _runtime(AnswerLlm(), FakeJudge()),
        on_stage=lambda key, status, ms, note: stages.append((key, status)),
    )  # fmt: skip
    assert not out.abstained and out.entities == [("raga", "Raga Securities and Finance Private Limited")]
    assert out.sources == ["SEBI"] and out.dense
    (claim,) = out.claims
    assert claim.verification == "entailed" and claim.evidence.doc_id == a.id
    assert ("retrieve", "done") in stages and ("answer", "done") in stages and ("verify", "done") in stages


def test_a_company_the_corpus_never_mentions_gets_an_abstention_not_a_guess(db):
    _seed(db)
    llm = AnswerLlm()
    out = answer_question(db, "What penalty did SEBI impose on Zenith Pharma?", _runtime(llm, FakeJudge()))
    assert out.abstained and "Zenith Pharma Limited" in out.reason and llm.calls == 0 and out.passages == []


def test_the_model_can_decline_and_the_sentences_it_saw_are_still_returned(db):
    _seed(db)
    out = answer_question(db, "What penalty did SEBI impose on Raga Securities?",
                          _runtime(AnswerLlm(decline=True), FakeJudge()))  # fmt: skip
    assert out.abstained and out.claims == [] and out.passages
    assert "do not answer" in out.reason


def test_without_a_model_server_the_retrieved_sentences_are_still_shown(db):
    _seed(db)
    out = answer_question(db, "penalty on Raga Securities", _runtime(None, FakeJudge()))
    assert out.abstained and out.passages and "not running" in out.reason


def test_without_an_nli_model_claims_stay_unverified(db):
    _seed(db)
    out = answer_question(db, "penalty on Raga Securities", _runtime(AnswerLlm(), None))
    assert [c.verification for c in out.claims] == ["unverified"] and out.claims[0].entail is None


# ------------------------------------------------------------------ API and worker


def test_asking_validates_the_question_and_queues_a_job(client, db):
    assert client.post("/api/ask", json={"question": "hi"}).status_code == 422
    assert client.post("/api/ask", json={"question": "x" * 600}).status_code == 422
    posted = client.post("/api/ask", json={"question": "  What   did SEBI do to Raga Securities?  "})
    assert posted.status_code == 202
    body = client.get(f"/api/ask/{posted.json()['jobId']}").json()
    assert body["status"] == "queued" and body["answer"] is None
    assert [s["key"] for s in body["stages"]] == ["retrieve", "answer", "verify"]
    assert db.scalar(select(Job.payload)) == {"question": "What did SEBI do to Raga Securities?"}
    assert client.get("/api/ask/not-a-job").status_code == 404


def test_the_worker_stores_the_answer_and_the_api_serves_it(client, db):
    _seed(db)
    job = enqueue(db, "ask", {"question": "What penalty did SEBI impose on Raga Securities?"})
    db.commit()
    claimed = claim_next(db)
    assert claimed is not None and claimed.id == job.id
    run_ask(db, claimed, _runtime(AnswerLlm(), FakeJudge()))
    body = client.get(f"/api/ask/{job.id}").json()
    assert body["status"] == "done" and {s["status"] for s in body["stages"]} == {"done"}
    answer_ = body["answer"]
    assert answer_["abstained"] is False and answer_["retrieval"] == "BM25 + dense, RRF"
    assert answer_["entities"][0]["id"] == "raga" and answer_["sources"] == ["SEBI"]
    (claim,) = answer_["claims"]
    assert (
        claim["verification"] == "entailed"
        and claim["evidence"]["documentTitle"] == "Order in the matter of Raga"
    )
    assert any(p["cited"] for p in answer_["passages"]) and answer_["passages"][0]["rank"] == 1
    # the evidence offsets slice back to the sentence in the filing
    doc = client.get(f"/api/documents/{claim['evidence']['documentId']}").json()
    assert doc["text"][claim["evidence"]["start"] : claim["evidence"]["end"]] == claim["evidence"]["text"]


def test_a_failed_ask_job_retries_with_the_ask_stages(db):
    job = enqueue(db, "ask", {"question": "What penalty did SEBI impose?"})
    db.commit()
    claimed = claim_next(db)
    assert [s["key"] for s in claimed.stages] == ["retrieve", "answer", "verify"]
    finish(db, claimed, error="boom")
    assert claimed.status == "queued" and [s["key"] for s in claimed.stages] == [
        "retrieve",
        "answer",
        "verify",
    ]
    assert next(s["key"] for s in new_stages()) == "ingest" and job.kind == "ask"


def test_suggestions_come_from_extracted_events(client, db):
    raga, venus, _, (a, _), (b, _), _ = _seed(db)
    db.add(Event(doc_id=a.id, entity_id=raga.id, type="SEBI Penalty", trigger_start=0, trigger_end=10,
                 event_date=date(2026, 10, 1), extractor="rules"))  # fmt: skip
    db.add(Event(doc_id=b.id, entity_id=venus.id, type="NCLT Admission", trigger_start=0, trigger_end=10,
                 event_date=date(2026, 10, 5), extractor="rules"))  # fmt: skip
    db.flush()
    assert client.get("/api/ask/suggestions").json() == [
        "Why was Venus Textiles Limited admitted into insolvency resolution?",
        "What action did SEBI take against Raga Securities and Finance Private Limited?",
    ]
