"""TF-IDF + logistic regression: the classical baseline for entity-level sentiment.

The input is the text in a window of +/-10 words around the entity, with the entity itself
replaced by a placeholder, so one sentence gives one prediction per entity and the model
cannot memorise company names. Word 1-2 grams and character 2-5 grams are combined.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion, Pipeline

from .data import LABELS

WINDOW = 10
PLACEHOLDER = "ENTITYX"
MODEL_NAME = "tfidf-lr"
_WORD = re.compile(r"\S+")


def window_text(text: str, start: int, end: int, k: int = WINDOW) -> str:
    """The k words either side of text[start:end], with the entity replaced by a placeholder."""
    before = _WORD.findall(text[:start])[-k:]
    after = _WORD.findall(text[end:])[:k]
    return " ".join([*before, PLACEHOLDER, *after])


def build_pipeline(c: float = 4.0) -> Pipeline:
    features = FeatureUnion(
        [
            ("word", TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True, lowercase=True)),
            ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), min_df=3, sublinear_tf=True)),
        ]
    )
    clf = LogisticRegression(C=c, class_weight="balanced", max_iter=2000, solver="lbfgs")
    return Pipeline([("features", features), ("clf", clf)])


class SentimentBaseline:
    def __init__(self, pipeline: Pipeline | None = None, version: str | None = None):
        self.pipeline = pipeline or build_pipeline()
        self.version = version

    def fit(self, windows: Sequence[str], labels: Sequence[str]) -> SentimentBaseline:
        self.pipeline.fit(list(windows), list(labels))
        digest = hashlib.sha1("\n".join(windows).encode("utf-8")).hexdigest()[:8]
        self.version = f"{MODEL_NAME}@{digest}"
        return self

    def predict_proba(self, windows: Sequence[str]) -> np.ndarray:
        """Probabilities in the order of `LABELS` (negative, neutral, positive)."""
        raw = self.pipeline.predict_proba(list(windows))
        order = [list(self.pipeline.classes_).index(lab) for lab in LABELS]
        return raw[:, order]

    def predict_spans(self, items: Sequence[tuple[str, int, int]]) -> np.ndarray:
        """Probabilities for (text, mention start, mention end) items, the interface every model shares."""
        return self.predict_proba([window_text(t, a, b) for t, a, b in items])

    def predict(self, windows: Sequence[str]) -> list[str]:
        return [LABELS[i] for i in self.predict_proba(windows).argmax(axis=1)]

    def save(self, directory: Path) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{self.version}.joblib"
        joblib.dump({"pipeline": self.pipeline, "version": self.version}, path)
        return path

    @classmethod
    def load(cls, path: Path) -> SentimentBaseline:
        blob: dict[str, Any] = joblib.load(path)
        return cls(blob["pipeline"], blob["version"])
