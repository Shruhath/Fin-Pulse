"""Summary evaluation on gold passages: ROUGE against human references, and attribution.

For each gold reference the system writes a summary from the passage's own sentences, so the
comparison is like for like. Reported: ROUGE-1/2/L F1; the share of claims that NLI says the passage
supports (attribution precision) and its complement (unsupported-claim rate); and the F1 between
the sentences the model cited and the ones the human cited. Lead-3 and LexRank are scored the same way.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from finpulse.db.models import Annotation, GoldPassage, Sentence
from finpulse.llm.client import Llm, LlmError
from finpulse.pipeline.verify import Judge, decide
from finpulse.summarize.llm import summarise
from finpulse.summarize.prune import lead_n, lexrank, usable

from .rouge import rouge


def import_references(session: Session, rows: list[dict[str, Any]]) -> int:
    """Store human reference summaries.

    Each row is {"passage_id", "annotator", "claims": [{"text", "sources": [sentence index in the passage]}]}.
    """
    added = 0
    for row in rows:
        passage = session.get(GoldPassage, int(row["passage_id"]))
        if passage is None or not row.get("claims"):
            continue
        exists = session.scalar(
            select(Annotation.id).where(
                Annotation.task == "summary",
                Annotation.label_source == "gold",
                Annotation.annotator == row["annotator"],
                Annotation.doc_id == passage.doc_id,
            )
        )
        if exists:
            continue
        session.add(
            Annotation(
                task="summary",
                doc_id=passage.doc_id,
                payload={"passage_id": passage.id, "claims": row["claims"]},
                label_source="gold",
                annotator=row["annotator"],
            )
        )
        added += 1
    session.flush()
    return added


def passage_sentences(session: Session, passage: GoldPassage) -> list[Sentence]:
    return [
        s
        for s in session.scalars(
            select(Sentence)
            .where(Sentence.doc_id == passage.doc_id, Sentence.char_start >= passage.char_start)
            .order_by(Sentence.idx)
        )
        if s.char_end <= passage.char_end
    ]


@dataclass(slots=True)
class SummaryScores:
    rouge1: list[float]
    rouge2: list[float]
    rougeL: list[float]
    attribution: list[float]
    citation_f1: list[float]

    def means(self) -> dict[str, float]:
        out = {
            "rouge1": mean(self.rouge1) if self.rouge1 else 0.0,
            "rouge2": mean(self.rouge2) if self.rouge2 else 0.0,
            "rougeL": mean(self.rougeL) if self.rougeL else 0.0,
            "n": float(len(self.rouge1)),
        }
        if self.attribution:
            out["attribution"] = mean(self.attribution)
            out["unsupported"] = 1.0 - out["attribution"]
        if self.citation_f1:
            out["citationF1"] = mean(self.citation_f1)
        return out


def _f1(a: set[int], b: set[int]) -> float:
    if not a and not b:
        return 1.0
    tp = len(a & b)
    return 0.0 if tp == 0 else 2 * tp / (len(a) + len(b))


def evaluate_summaries(
    session: Session, llm: Llm, model: str, judge: Judge | None
) -> dict[str, dict[str, float]]:
    """Scores for the LLM summary, Lead-3 and LexRank over every passage that has a human reference."""
    systems = {"llm": SummaryScores([], [], [], [], []), "lead3": SummaryScores([], [], [], [], []),
               "lexrank": SummaryScores([], [], [], [], [])}  # fmt: skip
    refs = session.scalars(
        select(Annotation).where(Annotation.task == "summary", Annotation.label_source == "gold")
    )
    for ref in refs:
        passage = session.get(GoldPassage, ref.payload["passage_id"])
        sentences = passage_sentences(session, passage) if passage else []
        if not sentences:
            continue
        texts = [s.text for s in sentences]
        reference = " ".join(c["text"] for c in ref.payload["claims"])
        gold_sources = {int(i) for c in ref.payload["claims"] for i in c.get("sources", [])}

        central = lexrank(texts)
        top = [i for i in sorted(range(len(texts)), key=lambda i: -central[i]) if usable(texts[i])][:3]
        for name, picks in (("lead3", lead_n(texts, 3)), ("lexrank", sorted(top))):
            r = rouge(" ".join(texts[i] for i in picks), reference)
            systems[name].rouge1.append(r["rouge1"])
            systems[name].rouge2.append(r["rouge2"])
            systems[name].rougeL.append(r["rougeL"])

        try:
            result = summarise(
                llm,
                model,
                subject="gold passage",
                scope="document",
                evidence=[(i, t) for i, t in enumerate(texts)],
            )
        except LlmError:
            continue
        r = rouge(" ".join(c.text for c in result.claims), reference)
        llm_scores = systems["llm"]
        llm_scores.rouge1.append(r["rouge1"])
        llm_scores.rouge2.append(r["rouge2"])
        llm_scores.rougeL.append(r["rougeL"])
        cited = {i for c in result.claims for i in c.sources}
        llm_scores.citation_f1.append(_f1(cited, gold_sources))
        if judge is not None:
            for claim in result.claims:
                probs = judge.predict([(t, claim.text) for t in texts])
                llm_scores.attribution.append(
                    1.0 if decide(float(probs[:, 0].max()), float(probs[:, 2].max())) == "entailed" else 0.0
                )
    return {name: scores.means() for name, scores in systems.items()}
