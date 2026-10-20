"""Exact-match span precision, recall and F1 (the strict, seqeval-style entity metric)."""

from __future__ import annotations

from collections.abc import Sequence


def span_scores(
    gold: Sequence[set[tuple[int, int]]], pred: Sequence[set[tuple[int, int]]]
) -> dict[str, float]:
    tp = sum(len(g & p) for g, p in zip(gold, pred, strict=True))
    n_pred = sum(len(p) for p in pred)
    n_gold = sum(len(g) for g in gold)
    precision = tp / n_pred if n_pred else 0.0
    recall = tp / n_gold if n_gold else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "spanPrecision": precision,
        "spanRecall": recall,
        "spanF1": f1,
        "n": float(len(gold)),
        "goldSpans": float(n_gold),
    }
