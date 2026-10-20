"""ROUGE-1, ROUGE-2 and ROUGE-L F1 on lower-cased word tokens (no stemming, no stop-word removal)."""

from __future__ import annotations

import re
from collections import Counter

_WORD = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> list[str]:
    return _WORD.findall(text.lower())


def _f1(overlap: float, cand: float, ref: float) -> float:
    if overlap == 0 or cand == 0 or ref == 0:
        return 0.0
    p, r = overlap / cand, overlap / ref
    return 2 * p * r / (p + r)


def rouge_n(candidate: str, reference: str, n: int) -> float:
    def grams(tokens: list[str]) -> Counter[tuple[str, ...]]:
        return Counter(tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1))

    c, r = grams(_tokens(candidate)), grams(_tokens(reference))
    return _f1(sum((c & r).values()), sum(c.values()), sum(r.values()))


def _lcs(a: list[str], b: list[str]) -> int:
    prev = [0] * (len(b) + 1)
    for x in a:
        cur = [0]
        for j, y in enumerate(b, start=1):
            cur.append(prev[j - 1] + 1 if x == y else max(prev[j], cur[-1]))
        prev = cur
    return prev[-1]


def rouge_l(candidate: str, reference: str) -> float:
    c, r = _tokens(candidate), _tokens(reference)
    return _f1(_lcs(c, r), len(c), len(r))


def rouge(candidate: str, reference: str) -> dict[str, float]:
    return {
        "rouge1": rouge_n(candidate, reference, 1),
        "rouge2": rouge_n(candidate, reference, 2),
        "rougeL": rouge_l(candidate, reference),
    }
