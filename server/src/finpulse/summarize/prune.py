"""Choose which sentences of a long document are shown to a model.

A SEBI order runs to thousands of words, more than a local 7B model reads well in one prompt.
Sentences are filtered for boilerplate and fragments, scored by LexRank (centrality in a TF-IDF
cosine graph), and kept best-first until a character budget is used. Sentences a rule has
already marked as operative are always kept. Original sentence indexes are preserved so a
model's `[S12]` citation points at the stored sentence.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

MIN_CHARS = 25
MAX_SENTENCES = 3000  # LexRank builds an n x n matrix
_BOILERPLATE = re.compile(
    r"^(?:date|place|sd/-|sd\.|signature|page\s+\d+|order\s+in\s+the\s+matter\s+of\s+.{0,60}\s+page\s+\d+|"
    r"\(?[a-z]\)?\s*$|annexure\b|\*+$)",
    re.IGNORECASE,
)


def usable(sentence: str) -> bool:
    """False for fragments, table rows (mostly digits) and signature or page furniture."""
    s = sentence.strip()
    if len(s) < MIN_CHARS or _BOILERPLATE.match(s):
        return False
    letters = sum(c.isalpha() for c in s)
    return letters / len(s) >= 0.55 and len(s.split()) >= 5


def lexrank(
    sentences: Sequence[str], *, threshold: float = 0.1, damping: float = 0.85, iterations: int = 60
) -> np.ndarray:
    """Centrality score per sentence, summing to 1."""
    n = len(sentences)
    if n == 0:
        return np.zeros(0)
    if n == 1:
        return np.ones(1)
    try:
        tfidf = TfidfVectorizer(stop_words="english", sublinear_tf=True).fit_transform(sentences)
    except ValueError:  # every sentence was stop words
        return np.full(n, 1.0 / n)
    sim = (tfidf @ tfidf.T).toarray()
    np.fill_diagonal(sim, 0.0)
    adj = (sim >= threshold).astype(float)
    degree = adj.sum(axis=1)
    transition = np.divide(adj, degree[:, None], out=np.full_like(adj, 1.0 / n), where=degree[:, None] > 0)
    scores = np.full(n, 1.0 / n)
    for _ in range(iterations):
        nxt = (1 - damping) / n + damping * transition.T @ scores
        if np.abs(nxt - scores).sum() < 1e-8:
            scores = nxt
            break
        scores = nxt
    return scores / scores.sum()


def select(sentences: Sequence[str], *, budget_chars: int, must_keep: Iterable[int] = ()) -> list[int]:
    """Indexes of the sentences to show, in document order, within `budget_chars` (must-keeps first)."""
    keep = {i for i in must_keep if 0 <= i < len(sentences)}
    used = sum(len(sentences[i]) + 8 for i in keep)
    candidates = [i for i, s in enumerate(sentences) if i not in keep and usable(s)][:MAX_SENTENCES]
    if candidates and used < budget_chars:
        scores = lexrank([sentences[i] for i in candidates])
        for pos in np.argsort(-scores, kind="stable"):
            i = candidates[int(pos)]
            cost = len(sentences[i]) + 8  # the "[S123] " prefix and newline
            if used + cost > budget_chars:
                continue
            keep.add(i)
            used += cost
    return sorted(keep)


def lead_n(sentences: Sequence[str], n: int = 3) -> list[int]:
    """The first n usable sentences: the Lead-3 baseline."""
    return [i for i, s in enumerate(sentences) if usable(s)][:n]
