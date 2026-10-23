"""Train and evaluate the entity-level sentiment baseline, and record the result.

Training uses the train split of FinEntity and SEntFiN together; every number reported comes
from the held-out test split of each dataset, separately. Each run writes a JSON file under
`ml/results/sentiment/` (committed, so a result is traceable to a commit) and one row per
dataset into `eval_results`. No metric reaches the UI without passing through here.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from finpulse.core.settings import REPO_DIR, get_settings
from finpulse.db.models import EvalResult
from finpulse.pipeline.runs import recorded_run
from finpulse.sentiment.baseline import MODEL_NAME, WINDOW, SentimentBaseline, window_text
from finpulse.sentiment.data import LABELS, Example, load_finentity, load_sentfin
from finpulse.sentiment.metrics import confusion, f1_scores, reliability

INDIAN = {"FinEntity": False, "SEntFiN": True}  # SEntFiN is Indian financial news


@dataclass(slots=True)
class SentimentRun:
    version: str
    model_path: Path
    result_path: Path
    rows: list[dict[str, Any]]


def _git_sha() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO_DIR, capture_output=True, text=True, check=True, timeout=10
        )
        return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def _windows(examples: list[Example]) -> list[str]:
    return [window_text(e.text, e.start, e.end) for e in examples]


def _data_hash(examples: list[Example]) -> str:
    h = hashlib.sha256()
    for e in sorted(examples, key=lambda e: (e.dataset, e.text, e.start)):
        h.update(f"{e.dataset}|{e.text}|{e.start}|{e.end}|{e.label}\n".encode())
    return h.hexdigest()


def evaluate(model: SentimentBaseline, examples: list[Example]) -> dict[str, Any]:
    probs = model.predict_proba(_windows(examples))
    pred = [LABELS[i] for i in probs.argmax(axis=1)]
    gold = [e.label for e in examples]
    cm = confusion(gold, pred)
    bins, ece = reliability(probs.max(axis=1).tolist(), [g == p for g, p in zip(gold, pred, strict=True)])
    return {
        "metrics": {**f1_scores(cm), "ece": ece, "n": float(len(examples))},
        "detail": {"labels": list(LABELS), "confusion": cm, "reliability": bins},
    }


def train_and_evaluate(session: Session, benchmark_dir: Path | None = None) -> SentimentRun:
    cfg = get_settings()
    root = benchmark_dir or cfg.benchmark_dir
    loaded = {"FinEntity": load_finentity(root), "SEntFiN": load_sentfin(root)}
    all_examples = [e for ld in loaded.values() for e in ld.examples]
    train = [e for e in all_examples if e.split == "train"]
    if not train:
        raise RuntimeError(f"no training examples found under {root}; run scripts/fetch_layer1.sh first")

    with recorded_run(
        session, "sentiment-train", model=MODEL_NAME, params={"window": WINDOW, "train": len(train)}
    ) as run:
        model = SentimentBaseline().fit(_windows(train), [e.label for e in train])
        data_hash = _data_hash(all_examples)
        sha = _git_sha()
        rows: list[dict[str, Any]] = []
        for name, ld in loaded.items():
            test = ld.by_split("test")
            if not test:
                continue
            result = evaluate(model, test)
            rows.append(
                {
                    "stage": "sentiment",
                    "model": f"TF-IDF + logistic regression ({model.version})",
                    "baseline": True,
                    "dataset": f"{name} test",
                    "split": "test",
                    "indian": INDIAN[name],
                    **result,
                    "counts": {s: len(ld.by_split(s)) for s in ("train", "dev", "test")},
                    "dropped": dict(ld.dropped),
                }
            )
            session.add(
                EvalResult(
                    stage="sentiment",
                    model=rows[-1]["model"],
                    baseline=True,
                    dataset=rows[-1]["dataset"],
                    split="test",
                    indian=INDIAN[name],
                    metrics=result["metrics"],
                    detail=result["detail"],
                    run_id=run.id,
                    git_sha=sha,
                    data_hash=data_hash,
                )
            )

        model_path = model.save(cfg.models_dir / "sentiment")
        out_dir = cfg.results_dir / "sentiment"
        out_dir.mkdir(parents=True, exist_ok=True)
        result_path = out_dir / f"{model.version.replace('@', '-')}.json"
        result_path.write_text(
            json.dumps(
                {
                    "model": MODEL_NAME,
                    "version": model.version,
                    "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
                    "git_sha": sha,
                    "data_hash": data_hash,
                    "window": WINDOW,
                    "train_examples": len(train),
                    "rows": rows,
                },
                indent=2,
            )
            + "\n"
        )
    return SentimentRun(model.version, model_path, result_path, rows)
