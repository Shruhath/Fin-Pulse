import json
import socket
import uuid

import httpx
import pymupdf
import pytest
from sqlalchemy import select

from finpulse.db.models import Document, Entity, Event, Job, Mention, MentionSentiment
from finpulse.ingest.fetch import FetchRefused, fetch
from finpulse.pipeline import analyze as analyze_mod
from finpulse.pipeline.analyze import run_analysis
from finpulse.pipeline.jobs import claim_next, enqueue, finish, new_stages
from finpulse.sentiment.baseline import SentimentBaseline, window_text
from finpulse.sentiment.data import Example

pytestmark = pytest.mark.db


@pytest.fixture(autouse=True)
def _no_llm_server(monkeypatch):
    """Tests never reach a real Ollama; the ones that want one install a fake."""
    monkeypatch.setattr(analyze_mod, "_llm_client", lambda: None)


ORDER = (
    "In the matter of Raga Securities and Finance Private Limited.\n\n"
    "20. In exercise of the powers conferred under section 15 I of the SEBI Act, I hereby impose a penalty "
    "of Rs. 4,00,000/- on the Noticee viz. Raga Securities and Finance Private Limited under section 15HB "
    "of SEBI Act. The company was penalised and fined heavily."
)


def test_posting_text_queues_a_job_and_reuses_the_document(client, db):
    first = client.post("/api/analyze", json={"text": ORDER, "source": "SEBI"})
    assert first.status_code == 202
    job = client.get(f"/api/jobs/{first.json()['jobId']}").json()
    assert job["status"] == "queued" and job["documentId"] is not None
    assert [s["key"] for s in job["stages"]] == [
        "ingest",
        "parse",
        "entities",
        "sentiment",
        "events",
        "summary",
        "verify",
    ]
    assert {s["status"] for s in job["stages"]} == {"pending"}

    second = client.post("/api/analyze", json={"text": ORDER, "source": "SEBI"}).json()
    other = client.get(f"/api/jobs/{second['jobId']}").json()
    assert other["documentId"] == job["documentId"] and other["id"] != job["id"]
    assert db.query(Document).count() == 1


def test_request_validation(client):
    assert client.post("/api/analyze", json={}).status_code == 422
    assert client.post("/api/analyze", json={"text": "  "}).status_code == 422
    assert client.post("/api/analyze", json={"text": "a", "url": "https://example.test"}).status_code == 422
    assert client.get("/api/jobs/not-a-uuid").status_code == 404
    assert client.get("/api/jobs/00000000-0000-0000-0000-000000000000").status_code == 404


def test_uploads_accept_pdf_and_html_only(client, tmp_path, monkeypatch):
    monkeypatch.setattr(analyze_mod.get_settings(), "data_dir", tmp_path)
    pdf = pymupdf.open()
    pdf.new_page().insert_text((72, 72), "A tiny order.", fontsize=12)
    data = pdf.tobytes()
    ok = client.post("/api/analyze/file", files={"file": ("order.pdf", data, "application/pdf")})
    assert ok.status_code == 202
    assert any((tmp_path / "raw" / "uploads").iterdir())
    assert (
        client.post("/api/analyze/file", files={"file": ("x.txt", b"hello", "text/plain")}).status_code == 415
    )
    assert (
        client.post("/api/analyze/file", files={"file": ("x.pdf", b"", "application/pdf")}).status_code == 422
    )


def _toy_model(tmp_path):
    ex = [
        Example(f"Firm{i} was penalised and fined", 0, 5 + len(str(i)), "negative", "t", "train")
        for i in range(30)
    ]
    ex += [
        Example(f"Firm{i} reported record profit", 0, 5 + len(str(i)), "positive", "t", "train")
        for i in range(30)
    ]
    ex += [
        Example(f"Firm{i} held a board meeting", 0, 5 + len(str(i)), "neutral", "t", "train")
        for i in range(30)
    ]
    model = SentimentBaseline().fit([window_text(e.text, e.start, e.end) for e in ex], [e.label for e in ex])
    return model


def _queued_job(client, db, text, source):
    job_id = client.post("/api/analyze", json={"text": text, "source": source}).json()["jobId"]
    return db.get(Job, uuid.UUID(job_id))


def test_full_analysis_without_a_sentiment_model_says_what_it_skipped(client, db, monkeypatch):
    monkeypatch.setattr(analyze_mod, "load_scoring_model", lambda **_: None)
    monkeypatch.setattr(analyze_mod, "_llm_client", lambda: None)
    job = _queued_job(client, db, ORDER, "SEBI")
    job.status, job.attempts = "running", 1
    run_analysis(db, job)

    stages = {s["key"]: s for s in job.stages}
    assert job.status == "done"
    assert [stages[k]["status"] for k in ("ingest", "parse", "entities")] == ["done"] * 3
    assert stages["sentiment"]["status"] == "skipped" and "no sentiment model" in stages["sentiment"]["note"]
    assert stages["events"]["status"] == "done" and "1 by rules" in stages["events"]["note"]
    assert stages["summary"]["status"] == "skipped"

    doc = db.get(Document, job.document_id)
    assert doc.status == "analysed" and doc.n_words > 10
    assert db.scalar(select(Event.type).where(Event.doc_id == doc.id)) == "SEBI Penalty"
    mention = db.scalars(select(Mention).where(Mention.doc_id == doc.id)).first()
    assert doc.clean_text[mention.char_start : mention.char_end] == mention.surface
    assert db.scalar(select(Entity).where(Entity.canonical_name.like("Raga Securities%"))) is not None


def test_full_analysis_scores_mentions_when_a_model_exists(client, db, monkeypatch, tmp_path):
    model = _toy_model(tmp_path)
    monkeypatch.setattr(analyze_mod, "load_scoring_model", lambda **_: model)
    job = _queued_job(client, db, ORDER, "SEBI")
    job.status, job.attempts = "running", 1
    run_analysis(db, job)
    stages = {s["key"]: s for s in job.stages}
    assert stages["sentiment"]["status"] == "done" and "scored by tfidf-lr@" in stages["sentiment"]["note"]
    scored = db.scalars(select(MentionSentiment)).all()
    assert scored and all(abs(m.p_pos + m.p_neg + m.p_neu - 1) < 1e-6 for m in scored)


def test_news_documents_skip_the_rule_events_with_a_reason(client, db, monkeypatch):
    monkeypatch.setattr(analyze_mod, "load_scoring_model", lambda **_: None)
    job = _queued_job(client, db, "Yes Bank shares rose on Monday after strong results.", "NEWS")
    job.status, job.attempts = "running", 1
    run_analysis(db, job)
    stages = {s["key"]: s for s in job.stages}
    assert stages["events"]["status"] == "skipped" and "SEBI, NCLT and RBI" in stages["events"]["note"]


def test_an_already_analysed_document_is_not_processed_twice(client, db, monkeypatch):
    monkeypatch.setattr(analyze_mod, "load_scoring_model", lambda **_: None)
    job = _queued_job(client, db, ORDER, "SEBI")
    job.status, job.attempts = "running", 1
    run_analysis(db, job)
    again = _queued_job(client, db, ORDER, "SEBI")
    again.status, again.attempts = "running", 1
    run_analysis(db, again)
    assert again.status == "done"
    later = [s for s in again.stages if s["key"] != "ingest"]
    assert {(s["status"], s["note"], s["ms"]) for s in later} == {("done", "already analysed", 0)}


def test_queue_claims_oldest_first_and_retries_then_fails(db):
    a = enqueue(db, "analyze", {})
    b = enqueue(db, "analyze", {})
    first = claim_next(db)
    assert first.id == a.id and first.status == "running" and first.attempts == 1
    assert claim_next(db).id == b.id
    assert claim_next(db) is None

    finish(db, first, error="boom")  # one attempt left of two
    assert first.status == "queued" and first.stages == new_stages()
    retried = claim_next(db)
    assert retried.id == a.id and retried.attempts == 2
    finish(db, retried, error="boom again")
    assert retried.status == "failed" and retried.error == "boom again" and retried.finished_at is not None


# ---------------------------------------------------------------- one-off URL fetch


def _public(monkeypatch, ip="93.184.216.34"):
    monkeypatch.setattr(socket, "getaddrinfo", lambda host, *_: [(socket.AF_INET, 0, 0, "", (ip, 0))])


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler), headers={"User-Agent": "test"})


def test_fetch_returns_the_page_when_robots_allows_it(monkeypatch):
    _public(monkeypatch)

    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /")
        return httpx.Response(
            200, text="<html><body><p>Hello</p></body></html>", headers={"content-type": "text/html"}
        )

    got = fetch("https://example.test/a", client=_client(handler))
    assert b"Hello" in got.body and not got.is_pdf


@pytest.mark.parametrize(
    ("url", "ip", "reason"),
    [
        ("ftp://example.test/a", "93.184.216.34", "only http and https"),
        ("http://intranet.test/a", "10.0.0.5", "public internet"),
        ("http://localhost.test/a", "127.0.0.1", "public internet"),
        ("http://meta.test/a", "169.254.169.254", "public internet"),
    ],
)
def test_fetch_refuses_non_public_targets(monkeypatch, url, ip, reason):
    _public(monkeypatch, ip)
    with pytest.raises(FetchRefused, match=reason):
        fetch(url, client=_client(lambda r: httpx.Response(200, text="x")))


def test_fetch_honours_robots_and_treats_an_unreadable_robots_as_a_refusal(monkeypatch):
    _public(monkeypatch)
    disallow = _client(lambda r: httpx.Response(200, text="User-agent: *\nDisallow: /"))
    with pytest.raises(FetchRefused, match=r"robots\.txt"):
        fetch("https://example.test/a", client=disallow)
    forbidden = _client(lambda r: httpx.Response(403))
    with pytest.raises(FetchRefused, match=r"robots\.txt"):
        fetch("https://example.test/a", client=forbidden)


def test_fetch_checks_redirect_targets_too(monkeypatch):
    calls = {"n": 0}

    def resolve(host, *_):
        calls["n"] += 1
        ip = "93.184.216.34" if host == "example.test" else "10.0.0.9"
        return [(socket.AF_INET, 0, 0, "", (ip, 0))]

    monkeypatch.setattr(socket, "getaddrinfo", resolve)

    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /")
        return httpx.Response(302, headers={"location": "http://internal.test/secret"})

    with pytest.raises(FetchRefused, match="public internet"):
        fetch("https://example.test/a", client=_client(handler))


def test_fetch_caps_the_download_size(monkeypatch):
    _public(monkeypatch)
    monkeypatch.setattr("finpulse.ingest.fetch.MAX_BYTES", 100)

    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /")
        return httpx.Response(200, content=b"x" * 500)

    with pytest.raises(FetchRefused, match="larger than"):
        fetch("https://example.test/big", client=_client(handler))


class _Server:
    """A fake Ollama: knows both models and answers events and summaries from scripts."""

    def __init__(self, event_answer, summary_answer):
        self.event_answer, self.summary_answer, self.calls = event_answer, summary_answer, []

    def models(self):
        return ["qwen2.5:7b-instruct", "llama3.1:8b-instruct-q4_K_M"]

    def has_model(self, name):
        return name in self.models()

    def chat(self, model, system, user, *, schema=None, num_predict=1024):
        from finpulse.llm.client import Reply

        self.calls.append(model)
        body = self.event_answer if "events" in schema["properties"] else self.summary_answer
        return Reply(json.dumps(body), model, 800, 60, 2.0)


def test_with_both_models_up_the_live_path_adds_llm_events_a_summary_and_verification(
    client, db, monkeypatch
):
    import numpy as np

    from finpulse.preprocess.sentences import split_sentences

    monkeypatch.setattr(analyze_mod, "load_scoring_model", lambda **_: None)
    impose = next(i for i, sp in enumerate(split_sentences(ORDER)) if "hereby impose" in sp.slice(ORDER))
    event = {
        "trigger_sentence_id": impose,
        "type": "SEBI Penalty",
        "entity": "Raga Securities and Finance Private Limited",
        "arguments": {"action": "penalty", "amount_inr": "Rs. 4,00,000/-"},
    }
    claim = {"text": "SEBI imposed a penalty of Rs. 4,00,000 on Raga.", "sources": []}
    server = _Server({"events": [event]}, {"claims": [claim]})
    monkeypatch.setattr(analyze_mod, "_llm_client", lambda: server)

    class Judge:
        name = "fake"

        def predict(self, pairs):
            return np.array([(0.95, 0.03, 0.02)] * len(pairs), dtype=np.float32)

    monkeypatch.setattr(analyze_mod, "_judge", lambda: Judge())
    job = _queued_job(client, db, ORDER, "SEBI")
    job.status, job.attempts = "running", 1
    run_analysis(db, job)

    stages = {s["key"]: s for s in job.stages}
    assert stages["events"]["status"] == "done" and "1 by rules" in stages["events"]["note"]
    assert "1 by qwen2.5:7b-instruct" in stages["events"]["note"]
    assert stages["summary"]["status"] == "done" and "1 claims" in stages["summary"]["note"]
    assert stages["verify"]["status"] == "done" and "1 entailed" in stages["verify"]["note"]
    assert server.calls == ["qwen2.5:7b-instruct", "llama3.1:8b-instruct-q4_K_M"]
    extractors = {e.extractor for e in db.scalars(select(Event).where(Event.doc_id == job.document_id))}
    assert extractors == {"rules", "llm"}


def test_news_gets_llm_events_but_no_rule_events_when_the_model_is_up(client, db, monkeypatch):
    monkeypatch.setattr(analyze_mod, "load_scoring_model", lambda **_: None)
    server = _Server({"events": []}, {"claims": []})
    monkeypatch.setattr(analyze_mod, "_llm_client", lambda: server)
    monkeypatch.setattr(analyze_mod, "_judge", lambda: None)
    job = _queued_job(
        client, db, "Yes Bank shares rose on Monday after the bank reported strong quarterly results.", "NEWS"
    )
    job.status, job.attempts = "running", 1
    run_analysis(db, job)
    stages = {s["key"]: s for s in job.stages}
    assert stages["events"]["note"] == "events: 0 by qwen2.5:7b-instruct"
    assert stages["verify"]["status"] == "skipped"  # no claims were produced


def test_a_full_queue_answers_429_instead_of_growing(client, db, monkeypatch):
    from finpulse.api.routers import analyze as router

    monkeypatch.setattr(router, "MAX_QUEUED", 2)
    for i in range(2):
        assert (
            client.post("/api/analyze", json={"text": f"Some text number {i} about Yes Bank."}).status_code
            == 202
        )
    full = client.post("/api/analyze", json={"text": "One more text about Yes Bank."})
    assert full.status_code == 429 and "queue is full" in full.json()["detail"]
