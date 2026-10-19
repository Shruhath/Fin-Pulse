"""Company-name normalisation shared by the gazetteer, the matcher and the resolver."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

LEGAL_SUFFIXES = frozenset(
    "limited ltd private pvt public llp inc incorporated corp corporation co company plc".split()
)
_LEADING = re.compile(r"^\s*(?:m/s\.?|messrs\.?|the)\s+", re.IGNORECASE)
_TOKEN = re.compile(r"[A-Za-z0-9]+(?:'[A-Za-z]+)?|&")


@dataclass(frozen=True, slots=True)
class Token:
    text: str
    start: int
    end: int

    @property
    def norm(self) -> str:
        return "and" if self.text == "&" else self.text.lower()


def tokenize(text: str) -> list[Token]:
    return [Token(m.group(0), m.start(), m.end()) for m in _TOKEN.finditer(text)]


def normalise_tokens(name: str) -> list[str]:
    """Lower-cased word tokens with '&' as 'and', a leading 'M/s' or 'The' and legal suffixes removed."""
    name = unicodedata.normalize("NFKC", name)
    name = _LEADING.sub("", name)
    words = [t.norm for t in tokenize(name)]
    trimmed = list(words)
    while trimmed and trimmed[-1] in LEGAL_SUFFIXES:
        trimmed.pop()
    return trimmed or words


def normalise_name(name: str) -> str:
    return " ".join(normalise_tokens(name))


def slugify(name: str) -> str:
    return "-".join(normalise_tokens(name)) or "entity"
