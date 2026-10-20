"""Company-name spans for training and scoring the NER models.

FinEntity (979 sentences, hand-labelled spans) and SEntFiN (Indian headlines, entity names located in
the title) both give character spans of company mentions. Sentences are cut into the word tokens of
`entities.names.tokenize` and tagged BIO. A span that does not start and end on token boundaries is
dropped and counted. Splits are the same hash split as the sentiment data, so no sentence is in two splits.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from finpulse.entities.names import Token, tokenize
from finpulse.sentiment.data import Loaded, load_finentity, load_sentfin

TAGS = ("O", "B-ORG", "I-ORG")


@dataclass(slots=True)
class Sentence:
    text: str
    tokens: list[Token]
    tags: list[str]
    split: str
    dataset: str

    def spans(self) -> set[tuple[int, int]]:
        return spans_from_tags(self.tokens, self.tags)


@dataclass(slots=True)
class NerData:
    sentences: list[Sentence] = field(default_factory=list)
    dropped: Counter[str] = field(default_factory=Counter)

    def by_split(self, split: str) -> list[Sentence]:
        return [s for s in self.sentences if s.split == split]


def spans_from_tags(tokens: list[Token], tags: list[str]) -> set[tuple[int, int]]:
    """Character spans of the entities a BIO tag sequence marks."""
    spans: set[tuple[int, int]] = set()
    start = end = None
    for tok, tag in zip(tokens, tags, strict=True):
        if tag == "B-ORG" or (tag == "I-ORG" and start is None):
            if start is not None:
                spans.add((start, end))
            start, end = tok.start, tok.end
        elif tag == "I-ORG":
            end = tok.end
        else:
            if start is not None:
                spans.add((start, end))
            start = end = None
    if start is not None:
        spans.add((start, end))
    return spans


def tags_from_spans(tokens: list[Token], spans: set[tuple[int, int]]) -> list[str] | None:
    """BIO tags for the tokens, or None when a span does not line up with token boundaries."""
    tags = ["O"] * len(tokens)
    for start, end in sorted(spans):
        inside = [i for i, t in enumerate(tokens) if t.start >= start and t.end <= end]
        if not inside or tokens[inside[0]].start != start or tokens[inside[-1]].end != end:
            return None
        if any(tags[i] != "O" for i in inside):
            return None  # overlapping spans
        tags[inside[0]] = "B-ORG"
        for i in inside[1:]:
            tags[i] = "I-ORG"
    return tags


def _add(loaded: Loaded, data: NerData) -> None:
    by_text: dict[str, set[tuple[int, int]]] = {}
    meta: dict[str, tuple[str, str]] = {}
    for ex in loaded.examples:
        by_text.setdefault(ex.text, set()).add((ex.start, ex.end))
        meta[ex.text] = (ex.split, ex.dataset)
    for text, spans in by_text.items():
        tokens = tokenize(text)
        tags = tags_from_spans(tokens, spans)
        if tags is None:
            data.dropped["span not on token boundaries"] += 1
            continue
        split, dataset = meta[text]
        data.sentences.append(Sentence(text, tokens, tags, split, dataset))


def load_ner_data(root: Path) -> NerData:
    data = NerData()
    _add(load_finentity(root), data)
    _add(load_sentfin(root), data)
    return data
