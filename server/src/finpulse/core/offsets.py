"""Character-offset helpers.

Every span in FinPulse (entity mentions, event triggers, evidence) is a half-open
[start, end) character range into `documents.clean_text`. The UI renders by slicing,
so these ranges must never be re-derived by searching for text.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Span:
    start: int
    end: int

    def __post_init__(self) -> None:
        if self.start < 0 or self.end < self.start:
            raise ValueError(f"invalid span [{self.start}, {self.end})")

    @property
    def length(self) -> int:
        return self.end - self.start

    def overlaps(self, other: Span) -> bool:
        return self.start < other.end and other.start < self.end

    def contains(self, other: Span) -> bool:
        return self.start <= other.start and other.end <= self.end

    def slice(self, text: str) -> str:
        return text[self.start : self.end]


def check_against(text: str, span: Span, surface: str) -> bool:
    """True when `text[span]` is exactly `surface`: the invariant every stored span must hold."""
    return span.end <= len(text) and span.slice(text) == surface


def drop_overlaps(spans: Iterable[Span]) -> list[Span]:
    """Keep the longest span of every overlapping group, ties going to the earliest."""
    kept: list[Span] = []
    for s in sorted(spans, key=lambda s: (-s.length, s.start)):
        if not any(s.overlaps(k) for k in kept):
            kept.append(s)
    return sorted(kept, key=lambda s: s.start)


def locate_sentence(sentences: list[Span], offset: int) -> int | None:
    """Index of the sentence containing `offset`, by binary search; None in a gap."""
    lo, hi = 0, len(sentences) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        s = sentences[mid]
        if offset < s.start:
            hi = mid - 1
        elif offset >= s.end:
            lo = mid + 1
        else:
            return mid
    return None
