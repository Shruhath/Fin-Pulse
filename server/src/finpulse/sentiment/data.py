"""Entity-level sentiment datasets: FinEntity (sentences with labelled spans) and SEntFiN (Indian
headlines with a label per named entity).

Neither ships a train/dev/test split we can rely on, so every example is assigned to a split by a
hash of its text: the assignment is the same on every machine and run, and a sentence never lands
in two splits. Examples whose entity cannot be located in the text are dropped and counted.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

LABELS = ("negative", "neutral", "positive")
FINENTITY = Path("finentity/FinEntity.json")
SENTFIN = Path("sentfin/SEntFiN.csv")

_PAIR = re.compile(r"(?:^\{|,\s*)'(.+?)':\s*'(positive|negative|neutral)'(?=\s*[,}])")


@dataclass(frozen=True, slots=True)
class Example:
    text: str
    start: int
    end: int
    label: str
    dataset: str
    split: str

    @property
    def surface(self) -> str:
        return self.text[self.start : self.end]


@dataclass(slots=True)
class Loaded:
    examples: list[Example] = field(default_factory=list)
    dropped: Counter[str] = field(default_factory=Counter)

    def by_split(self, split: str) -> list[Example]:
        return [e for e in self.examples if e.split == split]


def split_of(text: str) -> str:
    """80% train, 10% dev, 10% test, decided by the SHA-1 of the text."""
    bucket = int(hashlib.sha1(text.encode("utf-8")).hexdigest(), 16) % 10
    return "train" if bucket < 8 else "dev" if bucket == 8 else "test"


def _relocate(text: str, start: int, end: int, value: str) -> tuple[int, int] | None:
    """FinEntity offsets are occasionally shifted by a few characters; find the value nearest to them."""
    if text[start:end] == value:
        return start, end
    hits = [m.start() for m in re.finditer(re.escape(value), text)]
    if not hits:
        return None
    best = min(hits, key=lambda h: abs(h - start))
    return best, best + len(value)


def load_finentity(root: Path) -> Loaded:
    out = Loaded()
    if not (root / FINENTITY).is_file():
        out.dropped["file missing"] += 1
        return out
    for item in json.loads((root / FINENTITY).read_text(encoding="utf-8")):
        text = item["content"]
        for ann in item["annotations"]:
            span = _relocate(text, ann["start"], ann["end"], ann["value"])
            label = str(ann["tag"]).lower()
            if span is None or label not in LABELS:
                out.dropped["unlocatable" if span is None else "bad label"] += 1
                continue
            out.examples.append(Example(text, span[0], span[1], label, "FinEntity", split_of(text)))
    return out


def parse_decisions(raw: str) -> dict[str, str]:
    """SEntFiN's `Decisions` column is a Python-style dict whose names can contain apostrophes."""
    return {m.group(1): m.group(2) for m in _PAIR.finditer(raw.strip())}


def load_sentfin(root: Path) -> Loaded:
    out = Loaded()
    if not (root / SENTFIN).is_file():
        out.dropped["file missing"] += 1
        return out
    with (root / SENTFIN).open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            title = row["Title"].strip()
            for entity, label in parse_decisions(row["Decisions"]).items():
                at = title.lower().find(entity.lower())
                if at < 0:
                    out.dropped["entity not in title"] += 1
                    continue
                out.examples.append(Example(title, at, at + len(entity), label, "SEntFiN", split_of(title)))
    return out
