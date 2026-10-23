"""Metrics for the sentiment stage: F1, confusion matrix, expected calibration error."""

from __future__ import annotations

from collections.abc import Sequence
from itertools import pairwise

import numpy as np

from .data import LABELS


def confusion(gold: Sequence[str], pred: Sequence[str], labels: Sequence[str] = LABELS) -> list[list[int]]:
    """Rows are gold labels, columns are predicted labels."""
    index = {lab: i for i, lab in enumerate(labels)}
    m = [[0] * len(labels) for _ in labels]
    for g, p in zip(gold, pred, strict=True):
        m[index[g]][index[p]] += 1
    return m


def f1_scores(matrix: list[list[int]]) -> dict[str, float]:
    cm = np.asarray(matrix, dtype=float)
    tp = np.diag(cm)
    precision = np.divide(tp, cm.sum(axis=0), out=np.zeros_like(tp), where=cm.sum(axis=0) > 0)
    recall = np.divide(tp, cm.sum(axis=1), out=np.zeros_like(tp), where=cm.sum(axis=1) > 0)
    f1 = np.divide(
        2 * precision * recall, precision + recall, out=np.zeros_like(tp), where=(precision + recall) > 0
    )
    support = cm.sum(axis=1)
    total = support.sum()
    return {
        "macroF1": float(f1.mean()),
        "weightedF1": float((f1 * support).sum() / total) if total else 0.0,
        "accuracy": float(tp.sum() / total) if total else 0.0,
    }


def reliability(
    confidence: Sequence[float], correct: Sequence[bool], bins: int = 10
) -> tuple[list[dict[str, float]], float]:
    """Reliability bins (mean confidence, accuracy, count) and the expected calibration error."""
    conf = np.asarray(confidence, dtype=float)
    ok = np.asarray(correct, dtype=float)
    edges = np.linspace(0.0, 1.0, bins + 1)
    out: list[dict[str, float]] = []
    ece = 0.0
    for lo, hi in pairwise(edges):
        mask = (conf > lo) & (conf <= hi) if lo > 0 else (conf >= lo) & (conf <= hi)
        n = int(mask.sum())
        if n == 0:
            continue
        mean_conf, acc = float(conf[mask].mean()), float(ok[mask].mean())
        out.append({"confidence": mean_conf, "accuracy": acc, "n": n})
        ece += n / len(conf) * abs(acc - mean_conf)
    return out, float(ece)
