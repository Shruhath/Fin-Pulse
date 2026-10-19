"""Train and evaluate the entity-level sentiment models, and record every result.

Training uses the train split of FinEntity and SEntFiN together; every number reported comes from
the held-out test split of each dataset, separately. A run writes a JSON file under
`ml/results/sentiment/` (committed, so a result is traceable to a commit) and one row per model
and dataset into `eval_results`. No metric reaches the UI without passing through here.

Two models are compared:
  * `tfidf`: TF-IDF + logistic regression over a window around the entity (the classical baseline);
  * `finbert`: entity-marked ProsusAI/finbert, fine-tuned, temperature-calibrated on the dev split.
A FinBERT run also evaluates off-the-shelf FinBERT with no entity marking (the strawman a document-
level label would give) and tests FinBERT against the TF-IDF baseline with McNemar's exact test.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from sqlalchemy.orm import Session

from finpulse.core.settings import REPO_DIR, get_settings
from finpulse.db.models import EvalResult
from finpulse.pipeline.runs import recorded_run
from finpulse.sentiment.baseline import MODEL_NAME, WINDOW, SentimentBaseline, window_text
from finpulse.sentiment.data import LABELS, Example, Loaded, load_finentity, load_sentfin
from finpulse.sentiment.metrics import confusion, f1_scores, mcnemar, reliability

INDIAN = {"FinEntity": False, "SEntFiN": True}  # SEntFiN is Indian financial news


@dataclass(slots=True)
class SentimentRun:
    version: str
    model_path: Path
    result_path: Path
    rows: list[dict[str, Any]]


class SpanModel(Protocol):
    version: str | None

    def predict_spans(self, items: Sequence[tuple[str, int, int]]) -> Any: ...


def _git_sha() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO_DIR, capture_output=True, text=True, check=True, timeout=10
        )
        return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def _data_hash(examples: list[Example]) -> str:
    h = hashlib.sha256()
    for e in sorted(examples, key=lambda e: (e.dataset, e.text, e.start)):
        h.update(f"{e.dataset}|{e.text}|{e.start}|{e.end}|{e.label}\n".encode())
    return h.hexdigest()


def evaluate(model: SpanModel, examples: list[Example]) -> dict[str, Any]:
    """Metrics, confusion matrix and reliability bins of `model` on `examples`, plus its predictions."""
    probs = model.predict_spans([(e.text, e.start, e.end) for e in examples])
    pred = [LABELS[i] for i in probs.argmax(axis=1)]
    gold = [e.label for e in examples]
    cm = confusion(gold, pred)
    bins, ece = reliability(probs.max(axis=1).tolist(), [g == p for g, p in zip(gold, pred, strict=True)])
    return {
        "metrics": {**f1_scores(cm), "ece": ece, "n": float(len(examples))},
        "detail": {"labels": list(LABELS), "confusion": cm, "reliability": bins},
        "predictions": pred,
    }


def _load_data(root: Path) -> dict[str, Loaded]:
    return {"FinEntity": load_finentity(root), "SEntFiN": load_sentfin(root)}


def _row(
    model_name: str, baseline: bool, dataset: str, loaded: Loaded, result: dict[str, Any]
) -> dict[str, Any]:
    name = dataset.removesuffix(" test")
    return {
        "stage": "sentiment",
        "model": model_name,
        "baseline": baseline,
        "dataset": dataset,
        "split": "test",
        "indian": INDIAN[name],
        "metrics": result["metrics"],
        "detail": result["detail"],
        "counts": {s: len(loaded.by_split(s)) for s in ("train", "dev", "test")},
        "dropped": dict(loaded.dropped),
    }


def _train_tfidf(train: list[Example]) -> SentimentBaseline:
    return SentimentBaseline().fit(
        [window_text(e.text, e.start, e.end) for e in train], [e.label for e in train]
    )


def _tfidf_for_comparison(train: list[Example]) -> SentimentBaseline:
    """The newest saved TF-IDF model if there is one, so a FinBERT run compares against what is stored."""
    from finpulse.pipeline.sentiment import latest_model_path

    path = latest_model_path()
    return SentimentBaseline.load(path) if path else _train_tfidf(train)


def _finbert_rows(
    loaded: dict[str, Loaded], train: list[Example], dev: list[Example], epochs: int
) -> tuple[str, Path, list[dict[str, Any]], dict[str, Any]]:
    """Fine-tune FinBERT, save it, evaluate it and the off-the-shelf strawman. Frees the GPU afterwards."""
    from finpulse.neural.device import release
    from finpulse.sentiment.finbert import FinBert

    model = FinBert.from_base()
    report = model.fit(train, dev, epochs=epochs)
    version = model.version or "finbert-entity"
    path = model.save(get_settings().models_dir / "finbert" / version.replace("@", "-"))
    tfidf = _tfidf_for_comparison(train)
    rows: list[dict[str, Any]] = []
    for name, ld in loaded.items():
        test = ld.by_split("test")
        if not test:
            continue
        calibrated = evaluate(model, test)
        temperature, model.temperature = model.temperature, 1.0
        raw = evaluate(model, test)
        model.temperature = temperature
        detail = {**calibrated["detail"], "reliability_before": raw["detail"]["reliability"]}
        detail["mcnemar_vs_tfidf"] = mcnemar(
            [e.label for e in test], calibrated["predictions"], evaluate(tfidf, test)["predictions"]
        )
        result = {
            "metrics": {
                **calibrated["metrics"],
                "ece_before": raw["metrics"]["ece"],
                "temperature": temperature,
            },
            "detail": detail,
        }
        rows.append(_row(f"Entity-marked FinBERT, fine-tuned ({version})", False, f"{name} test", ld, result))
    del model
    release()

    # the strawman: off-the-shelf FinBERT, no entity marking, no fine-tuning
    zero = FinBert.from_base(entity_marked=False)
    for name, ld in loaded.items():
        test = ld.by_split("test")
        if test:
            rows.append(
                _row(
                    "FinBERT, sentence-level (off-the-shelf)", True, f"{name} test", ld, evaluate(zero, test)
                )
            )
    del zero
    release()
    summary = {"epochs": report.epochs, "best_epoch": report.best_epoch, "seconds": round(report.seconds, 1)}
    return version, path, rows, summary


def train_and_evaluate(
    session: Session, benchmark_dir: Path | None = None, *, kind: str = "tfidf", epochs: int = 4
) -> SentimentRun:
    cfg = get_settings()
    root = benchmark_dir or cfg.benchmark_dir
    loaded = _load_data(root)
    all_examples = [e for ld in loaded.values() for e in ld.examples]
    train = [e for e in all_examples if e.split == "train"]
    dev = [e for e in all_examples if e.split == "dev"]
    if not train:
        raise RuntimeError(f"no training examples found under {root}; run scripts/fetch_layer1.sh first")

    model_label = MODEL_NAME if kind == "tfidf" else "finbert-entity"
    params: dict[str, Any] = {"train": len(train), "dev": len(dev), "kind": kind}
    params.update({"window": WINDOW} if kind == "tfidf" else {"epochs": epochs})
    with recorded_run(session, "sentiment-train", model=model_label, params=params) as run:
        extra: dict[str, Any] = {}
        if kind == "tfidf":
            model = _train_tfidf(train)
            version = model.version or MODEL_NAME
            model_path = model.save(cfg.models_dir / "sentiment")
            rows = []
            for name, ld in loaded.items():
                test = ld.by_split("test")
                if test:
                    result = evaluate(model, test)
                    rows.append(
                        _row(f"TF-IDF + logistic regression ({version})", True, f"{name} test", ld, result)
                    )
        elif kind == "finbert":
            version, model_path, rows, extra = _finbert_rows(loaded, train, dev, epochs)
        else:
            raise ValueError(f"unknown model kind {kind!r}")

        sha, data_hash = _git_sha(), _data_hash(all_examples)
        for row in rows:
            session.add(
                EvalResult(
                    stage="sentiment",
                    model=row["model"],
                    baseline=row["baseline"],
                    dataset=row["dataset"],
                    split="test",
                    indian=row["indian"],
                    metrics=row["metrics"],
                    detail=row["detail"],
                    run_id=run.id,
                    git_sha=sha,
                    data_hash=data_hash,
                )
            )
        out_dir = cfg.results_dir / "sentiment"
        out_dir.mkdir(parents=True, exist_ok=True)
        result_path = out_dir / f"{version.replace('@', '-')}.json"
        result_path.write_text(
            json.dumps(
                {
                    "model": model_label,
                    "version": version,
                    "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
                    "git_sha": sha,
                    "data_hash": data_hash,
                    "train_examples": len(train),
                    "dev_examples": len(dev),
                    "training": extra,
                    "rows": rows,
                },
                indent=2,
            )
            + "\n"
        )
    return SentimentRun(version, model_path, result_path, rows)
