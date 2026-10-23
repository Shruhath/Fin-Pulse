"""Ablations: remove or replace one design choice at a time and measure what it was worth.

- Retrieval for Ask, on the silver questions: BM25 alone, dense (bge) alone, both fused (RRF), and each
  with and without the company and publisher filter taken from the question. Metric: hit@8, the share of
  questions whose relevant filing is among the top eight sentences, for questions that name a company and
  for questions that give only an amount. Runs on the CPU and needs no language model.
- Entity marking for sentiment: the same FinBERT fine-tuned on the same data, once with the company wrapped
  in marker tokens (the shipped model) and once on the plain sentence. Needs the GPU for about four minutes.

Results are written under `ml/results/ablation/`.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from finpulse.core.settings import get_settings
from finpulse.db.models import Sentence
from finpulse.eval.qa import build_questions
from finpulse.qa.question import parse_question
from finpulse.qa.retrieve import TOP_K, CorpusIndex, dense_ids, documents_for, retrieve

VARIANTS = (
    ("bm25", "BM25 only, no filter"),
    ("dense", "Dense (bge) only, no filter"),
    ("hybrid", "BM25 + dense fused, no filter"),
    ("bm25-filter", "BM25 with the company and publisher filter"),
    ("dense-filter", "Dense with the company and publisher filter"),
    ("hybrid-filter", "BM25 + dense fused with the filter (the shipped system)"),
)


def _docs_of_sentences(session: Session, ids: list[int]) -> set[int]:
    if not ids:
        return set()
    rows = dict(session.execute(select(Sentence.id, Sentence.doc_id).where(Sentence.id.in_(ids))).all())
    return {rows[i] for i in ids[:TOP_K] if i in rows}


def retrieval_ablation(session: Session, encoder: Any, n_each: int = 20) -> dict[str, dict[str, float]]:
    from finpulse.pipeline.ask import matcher_for

    index = CorpusIndex(session)
    matcher = matcher_for(session)
    questions = [q for q in build_questions(session, n_each=n_each) if q.kind in {"entity", "amount"}]
    hits: dict[str, dict[str, list[float]]] = {key: {"entity": [], "amount": []} for key, _ in VARIANTS}
    embed = getattr(encoder, "encode_queries", None) or encoder.encode
    for q in questions:
        vector = embed([q.text])[0]
        parsed = parse_question(q.text, matcher)
        scoped = documents_for(session, parsed.entity_ids, parsed.sources)
        for key, _ in VARIANTS:
            doc_filter = scoped if key.endswith("-filter") else None
            if key.startswith("dense"):
                found = _docs_of_sentences(session, dense_ids(session, vector, doc_filter))
            else:
                passages = retrieve(
                    session,
                    index,
                    q.text,
                    vector=vector if key.startswith("hybrid") else None,
                    doc_filter=doc_filter,
                    k=TOP_K,
                )
                found = {p.doc_id for p in passages}
            hits[key][q.kind].append(float(bool(found & q.relevant)))
    return {
        key: {kind: round(sum(v) / len(v), 4) if v else 0.0 for kind, v in per_kind.items()}
        | {"n": float(len(questions))}
        for key, per_kind in hits.items()
    }


def marking_ablation(root: Path, epochs: int = 4) -> dict[str, Any]:
    """Fine-tune FinBERT with and without entity markers on one split; score both on the test splits."""
    from finpulse.eval.sentiment import _load_data, evaluate
    from finpulse.neural.device import release
    from finpulse.sentiment.finbert import FinBert

    loaded = _load_data(root)
    all_examples = [e for ld in loaded.values() for e in ld.examples]
    train = [e for e in all_examples if e.split == "train"]
    dev = [e for e in all_examples if e.split == "dev"]
    out: dict[str, Any] = {}
    for key, marked in (("with-markers", True), ("without-markers", False)):
        model = FinBert.from_base(entity_marked=marked)
        report = model.fit(train, dev, epochs=epochs)
        out[key] = {
            "epochs": report.best_epoch,
            "seconds": round(report.seconds, 1),
            "temperature": report.temperature,
            **{
                name: evaluate(model, ld.by_split("test"))["metrics"]
                for name, ld in loaded.items()
                if ld.by_split("test")
            },
        }
        del model
        release()
    return out


def run_ablation(
    session: Session, results_dir: Path, *, which: set[str], encoder: Any | None = None
) -> dict[str, Any]:
    report: dict[str, Any] = {"generated_at": datetime.now(UTC).isoformat(timespec="seconds")}
    if "retrieval" in which:
        report["retrieval"] = retrieval_ablation(session, encoder)
    if "marking" in which:
        report["marking"] = marking_ablation(get_settings().benchmark_dir)
    out = results_dir / "ablation"
    out.mkdir(parents=True, exist_ok=True)
    name = "-".join(sorted(which))
    (out / f"{name}.json").write_text(json.dumps(report, indent=2) + "\n")
    return report
