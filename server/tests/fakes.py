"""Deterministic stand-ins for the neural encoders, so stage logic is tested without any model."""

from __future__ import annotations

import re
import zlib

import numpy as np

_WORD = re.compile(r"[a-z0-9]+")
_STOP = frozenset("a an and the of on in to was is by for under with that this".split())


def words(text: str) -> list[str]:
    return [w for w in _WORD.findall(text.lower()) if w not in _STOP]


class FakeEncoder:
    """Hashed bag-of-words vectors: sentences that share words are close in cosine distance."""

    name, dim = "fake-bow", 768

    def encode(self, texts):
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for row, text in enumerate(texts):
            for w in words(text):
                out[row, zlib.crc32(w.encode()) % self.dim] += 1.0
            norm = np.linalg.norm(out[row])
            if norm:
                out[row] /= norm
        return out


class FakeJudge:
    """Entails when the premise has the claim's words and numbers; contradicts when only numbers differ."""

    name = "fake-nli"

    def predict(self, pairs):
        rows = []
        for premise, claim in pairs:
            p, c = set(words(premise)), set(words(claim))
            overlap = len(p & c) / max(len(c), 1)
            numbers_ok = {w for w in c if w.isdigit()} <= p
            if overlap >= 0.8 and numbers_ok:
                rows.append((0.95, 0.03, 0.02))
            elif overlap >= 0.5 and not numbers_ok:
                rows.append((0.02, 0.08, 0.90))
            else:
                rows.append((0.10, 0.80, 0.10))
        return np.array(rows, dtype=np.float32)
