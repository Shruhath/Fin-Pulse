"""Rule layer: find known company names in text, as exact character spans.

A token trie over normalised alias tokens gives longest-match-wins scanning in one pass. This
plays the role of a spaCy EntityRuler without the dependency, and its matches double as silver
training data. Precision guards: every word of a match must start with a capital letter in the
source text, and short or single-word aliases need to be written in capitals or title case.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from finpulse.core.offsets import Span

from .names import LEGAL_SUFFIXES, Token, normalise_tokens, tokenize

_CONNECTORS = frozenset({"and", "of", "the", "for", "in", "&"})
# generic words that are valid NSE names on their own but are far more often ordinary words
GENERIC_ALIASES = frozenset(
    "page apollo century india indian bank national general united global premier prime star royal "
    "modern universal diamond golden sun pioneer advance alpha delta omega vision value".split()
)


@dataclass(slots=True)
class _Node:
    children: dict[str, _Node] = field(default_factory=dict)
    entity_ids: set[int] = field(default_factory=set)


@dataclass(frozen=True, slots=True)
class Match:
    span: Span
    surface: str
    entity_ids: tuple[int, ...]
    alias_tokens: tuple[str, ...]


class AliasMatcher:
    def __init__(self) -> None:
        self._root = _Node()
        self.size = 0

    def add(self, alias: str, entity_id: int) -> bool:
        toks = normalise_tokens(alias)
        if not toks or (len(toks) == 1 and (toks[0] in GENERIC_ALIASES or toks[0].isdigit())):
            return False
        node = self._root
        for t in toks:
            node = node.children.setdefault(t, _Node())
        if not node.entity_ids:
            self.size += 1
        node.entity_ids.add(entity_id)
        return True

    def extend(self, items: Iterable[tuple[str, int]]) -> None:
        for alias, entity_id in items:
            self.add(alias, entity_id)

    @staticmethod
    def _capitalised(tokens: list[Token]) -> bool:
        words = [t for t in tokens if t.text.lower() not in _CONNECTORS]
        return bool(words) and all(t.text[0].isupper() or t.text[0].isdigit() for t in words)

    def _longest(self, toks: list[Token], i: int) -> tuple[int, _Node] | None:
        node, best, j = self._root, None, i
        while j < len(toks) and toks[j].norm in node.children:
            node = node.children[toks[j].norm]
            j += 1
            if node.entity_ids:
                best = (j, node)
        return best

    def find(self, text: str) -> list[Match]:
        """Non-overlapping matches in text order, longest alias first."""
        toks = tokenize(text)
        out: list[Match] = []
        i = 0
        while i < len(toks):
            best = self._longest(toks, i)
            if best is None:
                i += 1
                continue
            stop, node = best
            matched = toks[i:stop]
            short = len(matched) == 1 and len(matched[0].text) <= 3 and not matched[0].text.isupper()
            if short or not self._capitalised(matched):
                i += 1
                continue
            end = stop
            # a legal suffix that follows ("Yes Bank" + "Limited") belongs to the mention
            while end < len(toks) and toks[end].norm in LEGAL_SUFFIXES and toks[end].text[0].isupper():
                end += 1
            span = Span(toks[i].start, toks[end - 1].end)
            out.append(
                Match(
                    span=span,
                    surface=text[span.start : span.end],
                    entity_ids=tuple(sorted(node.entity_ids)),
                    alias_tokens=tuple(t.norm for t in matched),
                )
            )
            i = end
        return out
