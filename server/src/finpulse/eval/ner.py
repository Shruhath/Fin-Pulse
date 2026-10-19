"""Train and evaluate the NER models, and record the results.

Three systems are scored on the held-out test split of FinEntity and of SEntFiN with exact-span F1:
the gazetteer rules (the matcher used in the pipeline), a CRF over word-shape and gazetteer features,
and a fine-tuned transformer token classifier.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from finpulse.core.settings import get_settings
from finpulse.db.models import EntityAlias, EvalResult
from finpulse.entities.matcher import AliasMatcher
from finpulse.ner.crf import CrfNer
from finpulse.ner.data import NerData, Sentence, load_ner_data
from finpulse.ner.metrics import span_scores
from finpulse.pipeline.runs import recorded_run

from .sentiment import INDIAN, _git_sha


@dataclass(slots=True)
class NerRun:
    version: str
    model_path: Path | None
    result_path: Path
    rows: list[dict[str, Any]]


def _score_rows(data: NerData, label: str, baseline: bool, predict) -> list[dict[str, Any]]:
    rows = []
    for dataset in ("FinEntity", "SEntFiN"):
        test = [s for s in data.by_split("test") if s.dataset == dataset]
        if test:
            gold = [s.spans() for s in test]
            pred = [{(a, b) for a, b in predict(s)} for s in test]
            rows.append(
                {
                    "stage": "ner",
                    "model": label,
                    "baseline": baseline,
                    "dataset": f"{dataset} test",
                    "indian": INDIAN[dataset],
                    "metrics": span_scores(gold, pred),
                }
            )
    return rows


def _clean_aliases(stmt):
    """SEntFiN's entity list was built from the same headlines the SEntFiN test split holds, so its aliases
    are left out of every gazetteer used here; only the NSE master and the corpus titles remain."""
    return stmt.where(EntityAlias.origin != "sentfin")


def gazetteer_predictor(session: Session):
    matcher = AliasMatcher()
    matcher.extend(session.execute(_clean_aliases(select(EntityAlias.alias, EntityAlias.entity_id))).all())
    return lambda s: [(m.span.start, m.span.end) for m in matcher.find(s.text)]


def train_and_evaluate(
    session: Session, benchmark_dir: Path | None = None, *, kind: str = "crf", epochs: int = 4
) -> NerRun:
    cfg = get_settings()
    data = load_ner_data(benchmark_dir or cfg.benchmark_dir)
    train, dev = data.by_split("train"), data.by_split("dev")
    if not train:
        raise RuntimeError("no NER training data found; run scripts/fetch_layer1.sh first")
    gazetteer = [a for (a,) in session.execute(_clean_aliases(select(EntityAlias.alias)))]

    with recorded_run(session, "ner-train", model=kind, params={"train": len(train), "dev": len(dev)}) as run:
        rows = _score_rows(data, "Gazetteer rules", True, gazetteer_predictor(session))
        extra: dict[str, Any] = {}
        model_path: Path | None = None
        if kind == "crf":
            crf = CrfNer(gazetteer).fit([(s.tokens, s.tags) for s in train])
            version = crf.version or "crf"
            model_path = crf.save(cfg.models_dir / "ner")
            rows += _score_rows(
                data,
                f"CRF + gazetteer ({version})",
                True,
                lambda s: [(a, b) for a, b, _ in crf.predict_spans(s.text)],
            )
        elif kind == "transformer":
            from finpulse.ner.transformer import TransformerNer
            from finpulse.neural.device import release

            model = TransformerNer.from_base()
            extra = model.fit(train, dev, epochs=epochs)
            version = model.version or "deberta-ner"
            model_path = model.save(cfg.models_dir / "ner-transformer" / version.replace("@", "-"))
            tests = data.by_split("test")
            spans = dict(zip(map(id, tests), model.predict_batch([s.text for s in tests]), strict=True))
            rows += _score_rows(
                data,
                f"DeBERTa-v3 token classifier ({version})",
                False,
                lambda s: [(a, b) for a, b, _ in spans[id(s)]],
            )
            del model
            release()
        else:
            raise ValueError(f"unknown NER model kind {kind!r}")

        sha, digest = _git_sha(), _data_hash_ner(data.sentences)
        for row in rows:
            session.add(
                EvalResult(
                    stage="ner",
                    model=row["model"],
                    baseline=row["baseline"],
                    dataset=row["dataset"],
                    split="test",
                    indian=row["indian"],
                    metrics=row["metrics"],
                    run_id=run.id,
                    git_sha=sha,
                    data_hash=digest,
                )
            )
        out = cfg.results_dir / "ner"
        out.mkdir(parents=True, exist_ok=True)
        result_path = out / f"{version.replace('@', '-')}.json"
        result_path.write_text(
            json.dumps(
                {
                    "version": version,
                    "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
                    "git_sha": sha,
                    "data_hash": digest,
                    "train_sentences": len(train),
                    "dropped": dict(data.dropped),
                    "training": extra,
                    "rows": rows,
                },
                indent=2,
            )
            + "\n"
        )
    return NerRun(version, model_path, result_path, rows)


def _data_hash_ner(sentences: list[Sentence]) -> str:
    import hashlib

    h = hashlib.sha256()
    for s in sorted(sentences, key=lambda s: (s.dataset, s.text)):
        h.update(f"{s.dataset}|{s.text}|{sorted(s.spans())}\n".encode())
    return h.hexdigest()
