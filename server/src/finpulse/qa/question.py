"""What a question asks about: the companies it names and the publishers it mentions.

Both narrow the search before any ranking happens. A company the gazetteer knows is found by the same
alias matcher the entity stage uses, so "what penalty did SEBI impose on rajesh exports" and the
capitalised form find the same company.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from finpulse.entities.matcher import AliasMatcher

_SOURCES = (
    ("SEBI", re.compile(r"\b(?:sebi|securities and exchange board)\b", re.IGNORECASE)),
    ("RBI", re.compile(r"\b(?:rbi|reserve bank)\b", re.IGNORECASE)),
    ("NCLT", re.compile(r"\b(?:nclt|ibbi|insolvency and bankruptcy board)\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class Parsed:
    entity_ids: tuple[int, ...]
    sources: tuple[str, ...]


# short or everyday words stay out of the second pass: "On" or "Order" must not name a company
_MIN_SINGLE_WORD = 5
_EVERYDAY = frozenset(
    "about after again before action against order orders under which where while would could should "
    "there their these those other another penalty notice number shares share price".split()
)


def _entity_ids(matcher: AliasMatcher, text: str, *, careful: bool = False) -> list[int]:
    found: list[int] = []
    for match in matcher.find(text):
        if len(match.entity_ids) != 1:
            continue  # an ambiguous alias names no one in particular
        if careful and len(match.alias_tokens) == 1:
            word = match.alias_tokens[0]
            if len(word) < _MIN_SINGLE_WORD or word in _EVERYDAY:
                continue
        if match.entity_ids[0] not in found:
            found.append(match.entity_ids[0])
    return found


def parse_question(question: str, matcher: AliasMatcher) -> Parsed:
    ids = _entity_ids(matcher, question)
    if not ids:
        # people type names in lower case; the matcher only trusts capitalised words, so try the
        # title-cased question, taking only names that cannot be everyday words
        ids = _entity_ids(matcher, question.title(), careful=True)
    sources = tuple(kind for kind, pattern in _SOURCES if pattern.search(question))
    return Parsed(tuple(ids), sources)
