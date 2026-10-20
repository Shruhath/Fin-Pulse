"""BM25 ranking and reciprocal rank fusion, written out so the retrieval step is auditable."""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Collection, Hashable, Sequence

_TOKEN = re.compile(r"[a-z0-9]+(?:\.[0-9]+)?")
_STOP = frozenset(
    "a an and are as at be by for from has have in is it its of on or that the this to was were with".split()
)


def tokens(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOP]


class BM25:
    def __init__(self, documents: Sequence[str], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.docs = [Counter(tokens(d)) for d in documents]
        self.lengths = [sum(c.values()) for c in self.docs]
        self.avg = (sum(self.lengths) / len(self.lengths)) if self.lengths else 0.0
        df: Counter[str] = Counter()
        for c in self.docs:
            df.update(c.keys())
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def scores(self, query: str, allowed: Collection[int] | None = None) -> list[float]:
        """A score per document; documents outside `allowed` (when given) score zero."""
        q = tokens(query)
        out = []
        for i, (counts, length) in enumerate(zip(self.docs, self.lengths, strict=True)):
            s = 0.0
            if allowed is not None and i not in allowed:
                out.append(s)
                continue
            for t in q:
                f = counts.get(t, 0)
                if f:
                    denom = f + self.k1 * (1 - self.b + self.b * length / (self.avg or 1.0))
                    s += self.idf[t] * f * (self.k1 + 1) / denom
            out.append(s)
        return out

    def rank(self, query: str, k: int = 20, allowed: Collection[int] | None = None) -> list[int]:
        """Indexes of the top k documents with a non-zero score, best first (ties keep document order)."""
        scores = self.scores(query, allowed)
        order = sorted(range(len(scores)), key=lambda i: (-scores[i], i))
        return [i for i in order[:k] if scores[i] > 0]


def rrf(rankings: Sequence[Sequence[Hashable]], k: int = 60) -> list[tuple[Hashable, float]]:
    """Reciprocal rank fusion: each list adds 1/(k + rank) to an item's score. Best first."""
    scores: dict[Hashable, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda kv: (-kv[1], str(kv[0])))
