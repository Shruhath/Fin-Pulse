"""Question answering over the corpus, scored on questions generated from its own extracted events.

No human wrote these questions or their answers, so every number here is a silver measurement and is
labelled that way. Four kinds of question:

  * entity  - "What action did SEBI take against X?" for a company with a rule-extracted event;
              relevant documents are those where X is a title party or has an event of that type;
  * amount  - "Which company was penalised ₹5 lakh by SEBI?"; relevant documents are the SEBI
              penalty events with that exact amount (no company is named, so retrieval has to find it);
  * absent  - the same question about a listed company no collected filing mentions: the right
              response is an abstention;
  * offtopic - "What is the share price target for X?" about a company that is in the corpus but whose
              filings say nothing about it: also an abstention.

Reported for the system: retrieval hit rate (a relevant document among the retrieved sentences), the
share of questions it answered, and of the answers' claims the share NLI finds supported or contradicted;
abstention rate on the unanswerable kinds. The baseline is BM25 over every sentence with no company
filter and no language model, on the same questions.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from statistics import median
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from finpulse.core.settings import get_settings
from finpulse.db.models import Document, Entity, EvalResult, Event, Mention
from finpulse.pipeline.ask import Runtime, answer_question
from finpulse.pipeline.link import NER_TITLE
from finpulse.pipeline.runs import recorded_run
from finpulse.preprocess.normalize import format_inr
from finpulse.qa.answer import PROMPT_VERSION
from finpulse.qa.retrieve import IN_CORPUS

DATASET = "FinPulse silver questions"
_TEMPLATES = {
    "SEBI Penalty": "What action did SEBI take against {entity}?",
    "NCLT Admission": "Why was {entity} admitted into insolvency resolution?",
    "RBI Action": "What action did the RBI take against {entity}?",
}


@dataclass(slots=True)
class Question:
    text: str
    kind: str  # entity | amount | absent | offtopic
    relevant: set[int] = field(default_factory=set)


def _pick(rows: list[Any], key: Any, n: int) -> list[Any]:
    """A deterministic sample: rows ordered by a hash of their key, so one corpus gives one question set."""
    return sorted(rows, key=lambda r: hashlib.sha256(str(key(r)).encode()).hexdigest())[:n]


def build_questions(session: Session, *, n_each: int = 20) -> list[Question]:
    questions: list[Question] = []

    # entity questions, from the rule-extracted events of companies
    events = session.execute(
        select(Event.entity_id, Event.type, Entity.canonical_name)
        .join(Entity, Entity.id == Event.entity_id)
        .join(Document, Document.id == Event.doc_id)
        .where(IN_CORPUS, Event.extractor == "rules", Event.type.in_(tuple(_TEMPLATES)))
        .where(Entity.kind.in_(("company", "bank")))
        .distinct()
    ).all()
    for entity_id, etype, name in _pick(events, lambda r: (r[0], r[1]), n_each):
        docs = set(
            session.scalars(select(Event.doc_id).where(Event.entity_id == entity_id, Event.type == etype))
        ) | set(
            session.scalars(
                select(Mention.doc_id).where(Mention.entity_id == entity_id, Mention.ner_model == NER_TITLE)
            )
        )
        questions.append(Question(_TEMPLATES[etype].format(entity=name), "entity", docs))

    # amount questions: no company named, the amount has to find the filing
    amounts = (
        session.execute(
            select(Event.amount_inr)
            .join(Document, Document.id == Event.doc_id)
            .where(IN_CORPUS, Event.type == "SEBI Penalty", Event.amount_inr.is_not(None))
            .distinct()
        )
        .scalars()
        .all()
    )
    for amount in _pick(list(amounts), lambda a: a, n_each):
        docs = set(
            session.scalars(
                select(Event.doc_id).where(Event.type == "SEBI Penalty", Event.amount_inr == Decimal(amount))
            )
        )
        questions.append(
            Question(f"Which company was penalised {format_inr(Decimal(amount))} by SEBI?", "amount", docs)
        )

    mentioned = select(Mention.entity_id).where(Mention.entity_id.is_not(None)).distinct()
    # absent: listed companies that no collected filing mentions
    absent = session.execute(
        select(Entity.slug, Entity.canonical_name).where(
            Entity.kind == "company", Entity.nse_symbol.is_not(None), Entity.id.not_in(mentioned)
        )
    ).all()
    for _, name in _pick(absent, lambda r: r[0], n_each):
        questions.append(Question(f"What penalty did SEBI impose on {name}?", "absent"))

    # off-topic: companies that are in the corpus, asked about something no filing discusses
    present = session.execute(
        select(Entity.slug, Entity.canonical_name).where(
            Entity.kind.in_(("company", "bank")), Entity.nse_symbol.is_not(None), Entity.id.in_(mentioned)
        )
    ).all()
    for _, name in _pick(present, lambda r: r[0], n_each):
        questions.append(Question(f"What is the share price target for {name}?", "offtopic"))
    return questions


@dataclass(slots=True)
class Scores:
    hits: dict[str, list[float]] = field(default_factory=dict)
    answered: list[float] = field(default_factory=list)
    claims: dict[str, int] = field(
        default_factory=lambda: {"entailed": 0, "contradicted": 0, "unverified": 0}
    )
    abstained: dict[str, list[float]] = field(default_factory=dict)
    seconds: list[float] = field(default_factory=list)


def _rate(values: list[float]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0


def evaluate_questions(
    session: Session, questions: list[Question], rt: Runtime
) -> tuple[dict[str, float], dict[str, float]]:
    """(system metrics, BM25 baseline metrics) over the same questions."""
    from finpulse.qa.retrieve import retrieve

    system, baseline = Scores(), Scores()
    index = rt.index(session)
    for q in questions:
        outcome = answer_question(session, q.text, rt)
        system.seconds.append(outcome.seconds)
        retrieved = {p.doc_id for p in outcome.passages}
        if q.kind in {"entity", "amount"}:
            system.hits.setdefault(q.kind, []).append(float(bool(retrieved & q.relevant)))
            system.answered.append(float(not outcome.abstained))
            for claim in outcome.claims:
                system.claims[claim.verification] += 1
            plain = retrieve(session, index, q.text, vector=None, doc_filter=None)
            baseline.hits.setdefault(q.kind, []).append(float(bool({p.doc_id for p in plain} & q.relevant)))
        else:
            system.abstained.setdefault(q.kind, []).append(float(outcome.abstained))

    judged = sum(system.claims.values())
    metrics = {
        "hitAt8Entity": _rate(system.hits.get("entity", [])),
        "hitAt8Amount": _rate(system.hits.get("amount", [])),
        "answered": _rate(system.answered),
        "claimsEntailed": round(system.claims["entailed"] / judged, 4) if judged else 0.0,
        "claimsContradicted": round(system.claims["contradicted"] / judged, 4) if judged else 0.0,
        "abstainAbsent": _rate(system.abstained.get("absent", [])),
        "abstainOfftopic": _rate(system.abstained.get("offtopic", [])),
        "medianSeconds": round(median(system.seconds), 2) if system.seconds else 0.0,
        "n": float(len(questions)),
    }
    base = {
        "hitAt8Entity": _rate(baseline.hits.get("entity", [])),
        "hitAt8Amount": _rate(baseline.hits.get("amount", [])),
        "n": float(len(questions)),
    }
    return metrics, base


def run_qa_eval(
    session: Session, rt: Runtime, *, n_each: int = 20
) -> tuple[dict[str, float], dict[str, float]]:
    from finpulse.eval.sentiment import _git_sha

    cfg = get_settings()
    questions = build_questions(session, n_each=n_each)
    if not questions:
        raise RuntimeError("the corpus has no extracted events to build questions from")
    kinds = {k: sum(q.kind == k for q in questions) for k in ("entity", "amount", "absent", "offtopic")}
    with recorded_run(
        session, "eval-qa", model=rt.model, prompt_version=PROMPT_VERSION, params={"questions": kinds}
    ) as run:
        system, base = evaluate_questions(session, questions, rt)
        sha = _git_sha()
        dataset = f"{DATASET} (n={len(questions)})"
        for label, baseline, metrics in (
            (f"{rt.model} + BM25/dense retrieval + NLI check", False, system),
            ("BM25 over all sentences, no company filter", True, base),
        ):
            session.add(
                EvalResult(
                    stage="qa", model=label, baseline=baseline, dataset=dataset, split="silver", indian=True,
                    metrics=metrics, run_id=run.id, git_sha=sha,
                )
            )  # fmt: skip
        out = cfg.results_dir / "qa"
        out.mkdir(parents=True, exist_ok=True)
        (out / f"qa-{datetime.now(UTC):%Y%m%dT%H%M%S}.json").write_text(
            json.dumps(
                {
                    "git_sha": sha,
                    "model": rt.model,
                    "prompt_version": PROMPT_VERSION,
                    "questions": kinds,
                    "system": system,
                    "baseline": base,
                    "examples": [
                        {"kind": q.kind, "text": q.text} for q in questions[:: max(1, len(questions) // 12)]
                    ],
                },
                indent=2,
            )
            + "\n"
        )
    return system, base
