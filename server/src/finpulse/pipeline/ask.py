"""Answer a question about the corpus: retrieve evidence, draft an answer from it, check every claim.

Three stages, reported to the job row as they finish: `retrieve` (the question's companies and
publishers narrow the search, then BM25 and dense search over every sentence are fused), `answer`
(the local Llama model writes claims that cite numbered sentences, or says the evidence does not
answer), and `verify` (NLI judges each claim against the sentences it cites and the best retrieved
ones). A question the corpus cannot answer ends in an abstention that says why, never in a guess.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from finpulse.core.settings import get_settings
from finpulse.db.models import Entity, EntityAlias, Job
from finpulse.entities.matcher import AliasMatcher
from finpulse.llm.client import Llm, LlmError, LlmUnavailable
from finpulse.qa.answer import PROMPT_VERSION, answer
from finpulse.qa.question import parse_question
from finpulse.qa.retrieve import TOP_K, CorpusIndex, Passage, documents_for, retrieve
from finpulse.summarize.llm import ClaimDraft

from .jobs import finish, set_stage
from .runs import recorded_run
from .verify import Judge, decide

log = logging.getLogger(__name__)

NLI_TOP = 2  # besides the sentences a claim cites, the best retrieved ones it is also checked against
MAX_QUESTION = 500

StageHook = Callable[[str, str, int | None, str | None], None]


@dataclass(slots=True)
class VerifiedClaim:
    text: str
    verification: str
    entail: float | None
    contradict: float | None
    evidence: Passage | None
    cited: list[int]


@dataclass(slots=True)
class Outcome:
    question: str
    entities: list[tuple[str, str]] = field(default_factory=list)  # (slug, name)
    sources: list[str] = field(default_factory=list)
    passages: list[Passage] = field(default_factory=list)
    claims: list[VerifiedClaim] = field(default_factory=list)
    abstained: bool = False
    reason: str | None = None
    model: str | None = None
    seconds: float = 0.0
    dense: bool = False


class Runtime:
    """The loaded models and indexes, kept between questions by the worker."""

    def __init__(self, llm: Llm | None, model: str, encoder: Any | None, judge: Judge | None):
        self.llm, self.model, self.encoder, self.judge = llm, model, encoder, judge
        self._index: CorpusIndex | None = None

    def index(self, session: Session) -> CorpusIndex:
        if self._index is None or not self._index.is_current(session):
            self._index = CorpusIndex(session)
        return self._index


def matcher_for(session: Session) -> AliasMatcher:
    matcher = AliasMatcher()
    matcher.extend(session.execute(select(EntityAlias.alias, EntityAlias.entity_id)).all())
    return matcher


def verify_claims(
    judge: Judge | None, drafts: list[ClaimDraft], passages: list[Passage]
) -> list[VerifiedClaim]:
    """NLI for each claim against the sentences it cites and the best few retrieved."""
    by_id = {p.sentence_id: p for p in passages}
    best = [p.sentence_id for p in passages[:NLI_TOP]]
    out: list[VerifiedClaim] = []
    for draft in drafts:
        cited = [i for i in draft.sources if i in by_id]
        ids = list(dict.fromkeys([*cited, *best]))
        if judge is None or not ids:
            first = by_id[cited[0]] if cited else None
            out.append(VerifiedClaim(draft.text, "unverified", None, None, first, cited))
            continue
        probs = judge.predict([(by_id[i].text, draft.text) for i in ids])
        entail_at, contra_at = int(np.argmax(probs[:, 0])), int(np.argmax(probs[:, 2]))
        label = decide(float(probs[entail_at, 0]), float(probs[contra_at, 2]))
        chosen = contra_at if label == "contradicted" else entail_at
        out.append(
            VerifiedClaim(
                draft.text, label, float(probs[chosen, 0]), float(probs[chosen, 2]), by_id[ids[chosen]], cited
            )
        )
    return out


def _entity_names(session: Session, ids: tuple[int, ...]) -> list[tuple[str, str]]:
    if not ids:
        return []
    rows = {
        e.id: (e.slug, e.canonical_name) for e in session.scalars(select(Entity).where(Entity.id.in_(ids)))
    }
    return [rows[i] for i in ids if i in rows]


def answer_question(
    session: Session, question: str, rt: Runtime, *, on_stage: StageHook | None = None
) -> Outcome:
    """Run the three stages for one question. Never raises for a question the corpus cannot answer."""
    hook = on_stage or (lambda key, status, ms, note: None)
    started = time.monotonic()
    out = Outcome(question=question, model=rt.model)

    def stage(key: str, work: Callable[[], str | None]) -> None:
        hook(key, "running", None, None)
        t0 = time.monotonic()
        note = work()
        hook(key, "done", int((time.monotonic() - t0) * 1000), note)

    def skip(keys: tuple[str, ...], why: str) -> None:
        for key in keys:
            hook(key, "skipped", None, why)

    def retrieve_stage() -> str | None:
        parsed = parse_question(question, matcher_for(session))
        out.entities = _entity_names(session, parsed.entity_ids)
        out.sources = list(parsed.sources)
        doc_filter = documents_for(session, parsed.entity_ids, parsed.sources)
        vector = None
        if rt.encoder is not None:
            embed_query = getattr(rt.encoder, "encode_queries", None) or rt.encoder.encode
            vector = embed_query([question])[0]
        out.dense = vector is not None
        out.passages = retrieve(
            session, rt.index(session), question, vector=vector, doc_filter=doc_filter, k=TOP_K
        )
        scope = ""
        if out.entities:
            scope += " about " + ", ".join(name for _, name in out.entities)
        if out.sources:
            scope += " from " + "/".join(out.sources)
        docs = len({p.doc_id for p in out.passages})
        return f"{len(out.passages)} sentences from {docs} documents{scope}"

    stage("retrieve", retrieve_stage)

    if not out.passages:
        out.abstained = True
        if out.entities:
            names = " or ".join(name for _, name in out.entities)
            out.reason = f"No collected filing mentions {names}."
        else:
            out.reason = "No sentence in the collected filings matches this question."
        skip(("answer", "verify"), "no evidence was retrieved")
        out.seconds = round(time.monotonic() - started, 2)
        return out

    if rt.llm is None:
        out.abstained = True
        out.reason = (
            f"The answer model {rt.model} is not running; these are the sentences it would have used."
        )
        skip(("answer", "verify"), "the local model server is not available")
        out.seconds = round(time.monotonic() - started, 2)
        return out

    drafts: list[ClaimDraft] = []

    def answer_stage() -> str | None:
        result = answer(rt.llm, rt.model, question, out.passages)
        if not result.answerable:
            out.abstained = True
            out.reason = "The retrieved sentences do not answer this question."
            return "the model found no answer in the evidence"
        drafts.extend(result.claims)
        return f"{len(result.claims)} claims from {len(out.passages)} sentences"

    try:
        stage("answer", answer_stage)
    except (LlmError, LlmUnavailable) as exc:
        out.abstained = True
        out.reason = f"The model gave no usable answer: {exc}"
        hook("answer", "failed", None, str(exc)[:200])
        skip(("verify",), "there was no answer to verify")
        out.seconds = round(time.monotonic() - started, 2)
        return out

    if not drafts:
        skip(("verify",), "nothing to verify")
    else:

        def verify_stage() -> str | None:
            out.claims = verify_claims(rt.judge, drafts, out.passages)
            tally = {
                k: sum(c.verification == k for c in out.claims)
                for k in ("entailed", "contradicted", "unverified")
            }
            suffix = "" if rt.judge is not None else " (the NLI model is not installed)"
            counts = ", ".join(f"{n} {label}" for label, n in tally.items())
            return counts + suffix

        stage("verify", verify_stage)
    out.seconds = round(time.monotonic() - started, 2)
    return out


def result_dict(out: Outcome) -> dict[str, Any]:
    """The stored form of an answer: exactly the fields the API serves."""
    cited = {i for c in out.claims for i in c.cited}

    def evidence(p: Passage) -> dict[str, Any]:
        return {
            "document_id": str(p.doc_id),
            "document_title": p.title,
            "source": p.source,
            "text": p.text,
            "start": p.char_start,
            "end": p.char_end,
        }

    return {
        "question": out.question,
        "abstained": out.abstained,
        "reason": out.reason,
        "entities": [{"id": slug, "name": name, "ticker": ""} for slug, name in out.entities],
        "sources": out.sources,
        "claims": [
            {
                "id": f"c{i}",
                "text": c.text,
                "verification": c.verification,
                "entail": c.entail,
                "contradict": c.contradict,
                "evidence": evidence(c.evidence) if c.evidence else None,
            }
            for i, c in enumerate(out.claims, start=1)
        ],
        "passages": [
            {
                **evidence(p),
                "rank": p.rank,
                "published_at": p.published_at.isoformat() if p.published_at else None,
                "cited": p.sentence_id in cited,
            }
            for p in out.passages
        ],
        "model": out.model,
        "prompt_version": PROMPT_VERSION,
        "seconds": out.seconds,
        "retrieval": "BM25 + dense, RRF" if out.dense else "BM25",
    }


_runtime: Runtime | None = None


def load_runtime() -> Runtime:
    """The models for answering, loaded once per worker process. Each part degrades on its own."""
    global _runtime
    if _runtime is None:
        from .analyze import _judge, _llm_client

        cfg = get_settings()
        llm = _llm_client()
        if llm is not None and not llm.has_model(cfg.summary_model):
            llm = None
        encoder = None
        try:
            from finpulse.embed.encoder import Embedder

            encoder = Embedder(device="cpu")  # the GPU stays free for the language model
        except ImportError:
            log.warning("the neural extra is not installed: answering with BM25 only")
        _runtime = Runtime(llm, cfg.summary_model, encoder, _judge())
    return _runtime


def run_ask(session: Session, job: Job, runtime: Runtime | None = None) -> None:
    """Answer the question in the job's payload and store the answer as the job's result."""
    question = str(job.payload.get("question", "")).strip()[:MAX_QUESTION]
    rt = runtime or load_runtime()

    def hook(key: str, status: str, ms: int | None, note: str | None) -> None:
        set_stage(session, job, key, status, ms=ms, note=note)

    with recorded_run(
        session,
        "ask",
        model=rt.model,
        prompt_version=PROMPT_VERSION,
        params={"question_chars": len(question)},
    ):
        outcome = answer_question(session, question, rt, on_stage=hook)
    job.result = result_dict(outcome)
    finish(session, job)
