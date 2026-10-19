"""Verify stage: retrieve evidence for each summary claim and judge it with NLI.

For a claim the candidates are the top fused hits from BM25 and dense search plus the sentences the
summariser cited. Each (evidence, claim) pair is scored; the claim is `entailed` when the best
evidence entails it with p >= 0.7, `contradicted` when some evidence contradicts it with p >= 0.7,
and `unverified` otherwise. Contradicted claims are kept and shown, never dropped.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Protocol

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from finpulse.db.models import Claim, Sentence, Summary
from finpulse.verify.retrieval import TOP_K, candidate_sentences, retrieve

from .embed import Encoder
from .runs import recorded_run

log = logging.getLogger(__name__)

ENTAIL_MIN = 0.7
CONTRADICT_MIN = 0.7


class Judge(Protocol):
    name: str

    def predict(self, pairs: list[tuple[str, str]]) -> np.ndarray:
        """Probabilities (entailment, neutral, contradiction) per (premise, hypothesis) pair."""


@dataclass(slots=True)
class VerifyStats:
    claims: int = 0
    entailed: int = 0
    contradicted: int = 0
    unverified: int = 0
    without_candidates: int = 0
    labels: dict[str, int] = field(default_factory=dict)


def decide(entail: float, contradict: float) -> str:
    if entail >= ENTAIL_MIN and entail >= contradict:
        return "entailed"
    if contradict >= CONTRADICT_MIN:
        return "contradicted"
    return "unverified"


def verify_claim(
    session: Session,
    judge: Judge,
    claim: Claim,
    candidates: list[tuple[int, str]],
    *,
    vector: np.ndarray | None = None,
) -> str:
    """Set the claim's verification, NLI scores and evidence; returns the label."""
    hits = retrieve(session, claim, candidates, vector=vector, k=TOP_K)
    rank_of = {h.sentence_id: h.rank for h in hits}
    text_of = dict(candidates)
    ids = list(dict.fromkeys([*(h.sentence_id for h in hits), *(c for c in claim.cited if c in text_of)]))
    if not ids:
        claim.verification, claim.nli_entail, claim.nli_contra = "unverified", None, None
        claim.evidence_sentence_id, claim.retrieval_rank = None, None
        return "unverified"
    probs = judge.predict([(text_of[i], claim.text) for i in ids])
    best_entail, best_contra = int(probs[:, 0].argmax()), int(probs[:, 2].argmax())
    label = decide(float(probs[best_entail, 0]), float(probs[best_contra, 2]))
    chosen = best_contra if label == "contradicted" else best_entail
    claim.verification = label
    claim.nli_entail, claim.nli_contra = float(probs[chosen, 0]), float(probs[chosen, 2])
    claim.evidence_sentence_id = ids[chosen]
    claim.retrieval_rank = rank_of.get(ids[chosen])
    return label


def verify_pending(
    session: Session,
    judge: Judge,
    encoder: Encoder | None = None,
    *,
    limit: int | None = None,
    redo: bool = False,
) -> VerifyStats:
    stmt = select(Summary).order_by(Summary.id)
    if not redo:
        stmt = stmt.where(
            select(Claim.id).where(Claim.summary_id == Summary.id, Claim.nli_entail.is_(None)).exists()
        )
    if limit:
        stmt = stmt.limit(limit)
    summaries = list(session.scalars(stmt))
    stats = VerifyStats()
    if not summaries:
        return stats
    with recorded_run(
        session,
        "verify",
        model=judge.name,
        params={"summaries": len(summaries), "entail_min": ENTAIL_MIN, "contradict_min": CONTRADICT_MIN,
                "dense": encoder is not None},
    ):  # fmt: skip
        for summary in summaries:
            candidates = candidate_sentences(session, summary)
            claims = list(
                session.scalars(select(Claim).where(Claim.summary_id == summary.id).order_by(Claim.idx))
            )
            vectors = encoder.encode([c.text for c in claims]) if encoder and claims else [None] * len(claims)
            for claim, vector in zip(claims, vectors, strict=True):
                if not redo and claim.nli_entail is not None:
                    continue
                label = verify_claim(session, judge, claim, candidates, vector=vector)
                stats.claims += 1
                stats.without_candidates += claim.evidence_sentence_id is None
                setattr(stats, label, getattr(stats, label) + 1)
            session.commit()
    return stats


def sentence_text(session: Session, sentence_id: int | None) -> str | None:
    return session.scalar(select(Sentence.text).where(Sentence.id == sentence_id)) if sentence_id else None
