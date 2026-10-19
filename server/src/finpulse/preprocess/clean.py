"""Turn parsed page text into the `clean_text` every span is measured against.

Cleaning happens once, before any entity or event is found, so offsets never need
translating back to the raw file. Paragraphs are separated by a blank line; lines inside a
paragraph are soft wraps and are joined with a single space.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Sequence

import ftfy

_PAGE_NUMBER = re.compile(r"^(?:page\s*)?\d{1,4}(?:\s*(?:of|/)\s*\d{1,4})?$|^-\s*\d{1,4}\s*-$", re.IGNORECASE)
_TERMINAL = re.compile(r"""[.!?:;)"'\]]$""")
_SPACES = re.compile(r"[ \t ]+")
_HYPHEN_WRAP = re.compile(r"(\w)-\n(?=[a-z])")
_FURNITURE_LINES = 3  # how many lines at the top and bottom of a page can be a header or footer


def fix_characters(raw: str) -> str:
    """Repair mojibake, normalise to NFKC and unify line endings. Never changes the words."""
    text = ftfy.fix_text(raw, normalization="NFKC")
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace(" ", "\n").replace("\x00", "")
    return text


def _furniture_key(line: str) -> str:
    return re.sub(r"\d+", "#", _SPACES.sub(" ", line.strip().lower()))


def strip_page_furniture(pages: Sequence[str]) -> list[str]:
    """Drop running headers, footers and page numbers.

    A line near the top or bottom of a page is furniture when its digit-normalised form
    recurs on at least half of the pages (needs three pages or more), or when it is a bare
    page number.
    """
    split = [p.split("\n") for p in pages]

    def edge_indexes(lines: list[str]) -> list[int]:
        filled = [i for i, ln in enumerate(lines) if ln.strip()]
        k = _FURNITURE_LINES if len(filled) > 2 * _FURNITURE_LINES else 1  # a short page is mostly body
        return filled[:k] + filled[-k:]

    counts: Counter[str] = Counter()
    for lines in split:
        keys = {_furniture_key(lines[i]) for i in edge_indexes(lines)}
        counts.update(keys)
    recurring = {k for k, n in counts.items() if len(pages) >= 3 and n >= len(pages) / 2 and k}

    cleaned: list[str] = []
    for lines in split:
        drop = set()
        for i in edge_indexes(lines):
            stripped = lines[i].strip()
            if _PAGE_NUMBER.match(stripped) or _furniture_key(lines[i]) in recurring:
                drop.add(i)
        cleaned.append("\n".join(ln for i, ln in enumerate(lines) if i not in drop))
    return cleaned


def paragraphs(page: str) -> list[str]:
    """Blank-line separated paragraphs, soft wraps joined, hyphenated line breaks repaired."""
    out: list[str] = []
    for chunk in re.split(r"\n[ \t]*\n+", page):
        chunk = _HYPHEN_WRAP.sub(r"\1", chunk)
        joined = _SPACES.sub(" ", chunk.replace("\n", " ")).strip()
        if joined:
            out.append(joined)
    return out


def clean_pages(pages: Sequence[str]) -> str:
    """The clean text of a multi-page document, with paragraphs split by a blank line."""
    fixed = [fix_characters(p) for p in pages]
    fixed = strip_page_furniture(fixed)
    merged: list[str] = []
    for page in fixed:
        for i, para in enumerate(paragraphs(page)):
            # a sentence running over a page break: no end punctuation, then a lowercase start
            if i == 0 and merged and not _TERMINAL.search(merged[-1]) and para[:1].islower():
                merged[-1] = f"{merged[-1]} {para}"
            else:
                merged.append(para)
    return "\n\n".join(merged)


def clean_text(raw: str) -> str:
    """Clean text that has no page structure (HTML extracts, pasted text)."""
    return clean_pages([raw])
