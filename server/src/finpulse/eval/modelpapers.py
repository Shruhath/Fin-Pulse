"""Comparison with the two model papers, and the extra classifier measures for the Evaluation page.

Model paper 1 (Krishnamoorthy, Knowl. Inf. Syst. 2018): a hierarchical sentiment classifier over
performance indicators (HSC), scored on Financial PhraseBank at four agreement levels with stratified
ten-fold cross-validation. We reproduce the protocol for our TF-IDF baseline and for off-the-shelf
FinBERT, and put the paper's published figures next to ours. ProsusAI/finbert was itself fine-tuned on
this dataset, so its row is a contaminated reference, not a fair test, and is labelled that way.

Model paper 2 (Yadav et al., Procedia CS 2020): an unsupervised semantic-orientation method (SO-PMI). We
re-implement it in a simplified form (word level, no part-of-speech patterns, seeds fixed in advance, the
neutral band tuned on the dev split) and score it on the SEntFiN test split next to the fine-tuned FinBERT.

`extend_sentiment_metrics` adds precision, recall and one-vs-rest AUC to the stored sentiment rows by
re-scoring the saved models on the same test splits; it refuses to change a row whose recomputed macro-F1
differs from the stored one, so it cannot drift from the numbers already reported.
"""

from __future__ import annotations

import contextlib
import json
import math
import re
import zipfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sqlalchemy import select
from sqlalchemy.orm import Session

from finpulse.db.models import EvalResult
from finpulse.sentiment.baseline import build_pipeline
from finpulse.sentiment.data import LABELS, Example, load_finentity, load_sentfin
from finpulse.sentiment.metrics import confusion, f1_scores

FPB_ZIP = Path("financial_phrasebank/data/FinancialPhraseBank-v1.0.zip")
FPB_LEVELS = {"DS100": "AllAgree", "DS75": "75Agree", "DS66": "66Agree", "DS50": "50Agree"}

# Published figures, Krishnamoorthy 2018, Table 5: per-class F-measure, order (positive, negative, neutral).
PUBLISHED_F = {
    "HSC (model paper 1, as published)": {
        "DS100": (0.83, 0.93, 0.83),
        "DS75": (0.76, 0.90, 0.80),
        "DS66": (0.72, 0.87, 0.77),
        "DS50": (0.69, 0.85, 0.75),
    },
    "LPS (Malo et al., as published in model paper 1)": {
        "DS100": (0.74, 0.86, 0.81),
        "DS75": (0.67, 0.83, 0.78),
        "DS66": (0.69, 0.77, 0.75),
        "DS50": (0.59, 0.78, 0.74),
    },
}

POS_SEEDS = frozenset(
    "rise rises gain gains profit surge growth up higher jump rally strong wins record".split()
)
NEG_SEEDS = frozenset("fall falls loss losses decline drop down lower slump plunge weak cut crash".split())
_STOP = frozenset("the a an of in on to for and at by with from as is are be its it this that".split())
_TOKEN = re.compile(r"[a-z][a-z'-]+")


def load_fpb(root: Path) -> dict[str, list[tuple[str, str]]]:
    """(sentence, label) for each agreement level of Financial PhraseBank."""
    out: dict[str, list[tuple[str, str]]] = {}
    with zipfile.ZipFile(root / FPB_ZIP) as z:
        for level, name in FPB_LEVELS.items():
            raw = z.read(f"FinancialPhraseBank-v1.0/Sentences_{name}.txt").decode("latin-1")
            rows = []
            for line in raw.splitlines():
                text, _, label = line.rpartition("@")
                if text and label.strip() in LABELS:
                    rows.append((text.strip(), label.strip()))
            out[level] = rows
    return out


def class_report(gold: list[str], probs: np.ndarray) -> dict[str, float]:
    """Accuracy, per-class and macro precision/recall/F1, and macro one-vs-rest AUC."""
    pred = [LABELS[i] for i in probs.argmax(axis=1)]
    cm = np.asarray(confusion(gold, pred), dtype=float)
    tp = np.diag(cm)
    precision = np.divide(tp, cm.sum(axis=0), out=np.zeros_like(tp), where=cm.sum(axis=0) > 0)
    recall = np.divide(tp, cm.sum(axis=1), out=np.zeros_like(tp), where=cm.sum(axis=1) > 0)
    out = {
        **f1_scores(cm.astype(int).tolist()),
        "precisionMacro": float(precision.mean()),
        "recallMacro": float(recall.mean()),
        "n": float(len(gold)),
    }
    onehot = np.eye(len(LABELS))[[LABELS.index(g) for g in gold]]
    with contextlib.suppress(ValueError):  # a class is missing from the gold labels
        out["aucMacro"] = float(roc_auc_score(onehot, probs, average="macro"))
    f1 = np.divide(
        2 * precision * recall, precision + recall, out=np.zeros_like(tp), where=(precision + recall) > 0
    )
    out.update({f"f1_{lab}": float(f) for lab, f in zip(LABELS, f1, strict=True)})
    return out


def published_macro(per_class: tuple[float, float, float]) -> float:
    return sum(per_class) / 3


def fpb_cross_validation(
    data: dict[str, list[tuple[str, str]]], *, folds: int = 10, seed: int = 7
) -> dict[str, Any]:
    """TF-IDF + logistic regression, stratified ten-fold, at each agreement level."""
    out: dict[str, Any] = {}
    for level, rows in data.items():
        texts = [t for t, _ in rows]
        labels = [lab for _, lab in rows]
        skf = StratifiedKFold(n_splits=folds, shuffle=True, random_state=seed)
        probs = cross_val_predict(build_pipeline(), texts, labels, cv=skf, method="predict_proba", n_jobs=4)
        classes = list(sorted(set(labels)))
        ordered = np.zeros((len(texts), len(LABELS)))
        for j, lab in enumerate(classes):
            ordered[:, LABELS.index(lab)] = probs[:, j]
        out[level] = class_report(labels, ordered)
    return out


def fpb_zero_shot(data: dict[str, list[tuple[str, str]]], *, device: str = "cpu") -> dict[str, Any]:
    """Off-the-shelf ProsusAI/finbert per level; it was trained on this dataset, so it is a reference only."""
    from finpulse.sentiment.finbert import FinBert

    model = FinBert.from_base(entity_marked=False, device=device)
    widest = data["DS50"]
    probs = model.predict_spans([(t, 0, 0) for t, _ in widest])
    by_text = {t: probs[i] for i, (t, _) in enumerate(widest)}
    return {
        level: class_report([lab for _, lab in rows], np.vstack([by_text[t] for t, _ in rows]))
        for level, rows in data.items()
    }


class SoPmi:
    """Semantic orientation by PMI against fixed seed words, averaged over a text's words (Turney-style)."""

    def __init__(self, titles: list[str], min_df: int = 3):
        self.n = len(titles)
        df: Counter[str] = Counter()
        pos: Counter[str] = Counter()
        neg: Counter[str] = Counter()
        pos_docs = neg_docs = 0
        for title in titles:
            words = set(_TOKEN.findall(title.lower())) - _STOP
            has_pos, has_neg = bool(words & POS_SEEDS), bool(words & NEG_SEEDS)
            pos_docs += has_pos
            neg_docs += has_neg
            for w in words:
                df[w] += 1
                pos[w] += has_pos
                neg[w] += has_neg
        self.so = {
            w: math.log2(((pos[w] + 0.5) * (neg_docs + 0.5)) / ((neg[w] + 0.5) * (pos_docs + 0.5)))
            for w, c in df.items()
            if c >= min_df and w not in POS_SEEDS | NEG_SEEDS
        }

    def score(self, text: str) -> float:
        vals = [self.so[w] for w in set(_TOKEN.findall(text.lower())) - _STOP if w in self.so]
        return sum(vals) / len(vals) if vals else 0.0

    @staticmethod
    def label(score: float, band: float) -> str:
        return "positive" if score > band else "negative" if score < -band else "neutral"


def so_pmi_on_sentfin(root: Path) -> dict[str, Any]:
    loaded = load_sentfin(root)
    train = [e for e in loaded.examples if e.split == "train"]
    dev = [e for e in loaded.examples if e.split == "dev"]
    test = [e for e in loaded.examples if e.split == "test"]
    model = SoPmi(sorted({e.text for e in train}))

    def macro(examples: list[Example], band: float) -> float:
        gold = [e.label for e in examples]
        pred = [SoPmi.label(model.score(e.text), band) for e in examples]
        return f1_scores(confusion(gold, pred))["macroF1"]

    band = max((b / 4 for b in range(0, 13)), key=lambda b: macro(dev, b))
    gold = [e.label for e in test]
    pred = [SoPmi.label(model.score(e.text), band) for e in test]
    return {**f1_scores(confusion(gold, pred)), "n": float(len(test)), "neutralBand": band}


def run_model_papers(root: Path, results_dir: Path, *, device: str = "cpu") -> dict[str, Any]:
    data = load_fpb(root)
    published = {
        name: {
            level: {
                "macroF1": published_macro(v),
                "perClassF1": dict(zip(("positive", "negative", "neutral"), v, strict=True)),
            }
            for level, v in levels.items()
        }
        for name, levels in PUBLISHED_F.items()
    }
    report = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "protocol": "Financial PhraseBank, stratified 10-fold cross-validation, seed 7",
        "sizes": {level: len(rows) for level, rows in data.items()},
        "published": published,
        "tfidf_lr": fpb_cross_validation(data),
        "finbert_off_the_shelf": fpb_zero_shot(data, device=device),
        "so_pmi_sentfin_test": so_pmi_on_sentfin(root),
    }
    out = results_dir / "model-papers"
    out.mkdir(parents=True, exist_ok=True)
    (out / "comparison.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def _score_models(root: Path, device: str) -> dict[str, dict[str, tuple[np.ndarray, list[str]]]]:
    """Probabilities of each saved model on each test split: {model kind: {dataset: (probs, gold)}}."""
    from finpulse.pipeline.sentiment import latest_model_path, load_scoring_model
    from finpulse.sentiment.baseline import SentimentBaseline
    from finpulse.sentiment.finbert import FinBert

    sets = {
        "FinEntity test": load_finentity(root).by_split("test"),
        "SEntFiN test": load_sentfin(root).by_split("test"),
    }
    finbert = load_scoring_model(device=device)
    if not isinstance(finbert, FinBert):
        raise RuntimeError("the fine-tuned FinBERT is not on disk")
    tfidf = SentimentBaseline.load(latest_model_path())  # type: ignore[arg-type]
    zero = FinBert.from_base(entity_marked=False, device=device)
    out: dict[str, dict[str, tuple[np.ndarray, list[str]]]] = {"finbert": {}, "tfidf": {}, "zero": {}}
    for name, test in sets.items():
        items = [(e.text, e.start, e.end) for e in test]
        gold = [e.label for e in test]
        out["finbert"][name] = (finbert.predict_spans(items), gold)
        out["tfidf"][name] = (tfidf.predict_spans(items), gold)
        out["zero"][name] = (zero.predict_spans(items), gold)
    return out


def extend_sentiment_metrics(session: Session, root: Path, *, device: str = "cpu") -> list[str]:
    """Add precision, recall and AUC to the stored sentiment rows. Returns what it changed."""
    scored = _score_models(root, device)
    prefix = {"finbert": "Entity-marked FinBERT", "tfidf": "TF-IDF", "zero": "FinBERT, sentence-level"}
    changed: list[str] = []
    for kind, per_dataset in scored.items():
        for dataset, (probs, gold) in per_dataset.items():
            report = class_report(gold, probs)
            for row in session.scalars(
                select(EvalResult).where(EvalResult.stage == "sentiment", EvalResult.dataset == dataset)
            ):
                if not row.model.startswith(prefix[kind]):
                    continue
                if abs(row.metrics["macroF1"] - report["macroF1"]) > 0.005:
                    stored, again = row.metrics["macroF1"], report["macroF1"]
                    raise RuntimeError(
                        f"{row.model} on {dataset}: stored macro-F1 {stored:.3f}, recomputed {again:.3f}"
                    )
                row.metrics = {
                    **row.metrics,
                    **{k: v for k, v in report.items() if k in ("precisionMacro", "recallMacro", "aucMacro")},
                }
                changed.append(f"{row.model} / {dataset}")
    session.commit()
    return changed
