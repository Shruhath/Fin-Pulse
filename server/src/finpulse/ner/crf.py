"""Classical NER baseline: a linear-chain CRF over word-shape, affix, context and gazetteer features."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Sequence
from pathlib import Path

import joblib
import sklearn_crfsuite

from finpulse.entities.names import LEGAL_SUFFIXES, Token, tokenize

MODEL_NAME = "crf-gazetteer"


def shape(word: str) -> str:
    s = re.sub(r"[A-Z]", "X", word)
    s = re.sub(r"[a-z]", "x", s)
    s = re.sub(r"[0-9]", "d", s)
    return re.sub(r"(.)\1{2,}", r"\1\1", s)  # collapse long runs


def _word_features(
    tokens: Sequence[Token], i: int, gaz_first: set[str], gaz_all: set[str]
) -> dict[str, object]:
    w = tokens[i].text
    low = tokens[i].norm
    feats: dict[str, object] = {
        "bias": 1.0,
        "w": low,
        "shape": shape(w),
        "p2": low[:2],
        "p3": low[:3],
        "s2": low[-2:],
        "s3": low[-3:],
        "title": w[:1].isupper(),
        "upper": w.isupper() and len(w) > 1,
        "digit": w.isdigit(),
        "len": min(len(w), 8),
        "legal": low in LEGAL_SUFFIXES,
        "gaz_first": low in gaz_first,
        "gaz_any": low in gaz_all,
        "first": i == 0,
    }
    for off in (-2, -1, 1, 2):
        j = i + off
        if 0 <= j < len(tokens):
            t = tokens[j]
            feats.update(
                {
                    f"{off}:w": t.norm,
                    f"{off}:shape": shape(t.text),
                    f"{off}:title": t.text[:1].isupper(),
                    f"{off}:legal": t.norm in LEGAL_SUFFIXES,
                    f"{off}:gaz": t.norm in gaz_all,
                }
            )
        else:
            feats[f"{off}:edge"] = True
    return feats


class CrfNer:
    def __init__(
        self, gazetteer: Iterable[str] = (), *, c1: float = 0.05, c2: float = 0.05, max_iterations: int = 150
    ):
        self.gaz_first: set[str] = set()
        self.gaz_all: set[str] = set()
        for name in gazetteer:
            toks = [t.norm for t in tokenize(name)]
            if toks:
                self.gaz_first.add(toks[0])
                self.gaz_all.update(toks)
        self.crf = sklearn_crfsuite.CRF(
            algorithm="lbfgs", c1=c1, c2=c2, max_iterations=max_iterations, all_possible_transitions=True
        )
        self.version: str | None = None

    def _features(self, tokens: Sequence[Token]) -> list[dict[str, object]]:
        return [_word_features(tokens, i, self.gaz_first, self.gaz_all) for i in range(len(tokens))]

    def fit(self, sentences: Sequence[tuple[Sequence[Token], Sequence[str]]]) -> CrfNer:
        self.crf.fit([self._features(t) for t, _ in sentences], [list(tags) for _, tags in sentences])
        digest = hashlib.sha1(
            "|".join(" ".join(t.text for t in toks) for toks, _ in sentences).encode()
        ).hexdigest()[:8]
        self.version = f"{MODEL_NAME}@{digest}"
        return self

    def predict_tags(self, tokens: Sequence[Token]) -> list[str]:
        return self.crf.predict_single(self._features(tokens)) if tokens else []

    def predict_spans(self, text: str) -> list[tuple[int, int, float]]:
        """(start, end, marginal probability of the span's first tag) for every entity in `text`."""
        from .data import spans_from_tags

        tokens = tokenize(text)
        if not tokens:
            return []
        tags = self.predict_tags(tokens)
        marginals = self.crf.predict_marginals_single(self._features(tokens))
        out = []
        for start, end in sorted(spans_from_tags(tokens, tags)):
            first = next(i for i, t in enumerate(tokens) if t.start == start)
            out.append((start, end, float(marginals[first][tags[first]])))
        return out

    def predict_batch(self, texts: Sequence[str]) -> list[list[tuple[int, int, float]]]:
        return [self.predict_spans(t) for t in texts]

    def save(self, directory: Path) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{self.version}.joblib"
        joblib.dump(self, path)
        return path

    @classmethod
    def load(cls, path: Path) -> CrfNer:
        return joblib.load(path)
