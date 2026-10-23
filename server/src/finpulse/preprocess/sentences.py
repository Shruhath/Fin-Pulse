"""Rule-based sentence splitter for Indian legal and financial text.

Returns character spans into the text it was given, so sentence offsets line up with
`documents.clean_text`. The hard cases are abbreviations ("Ltd.", "Rs.", "No.", "Shri"),
initials ("A. K. Gupta"), numbered paragraphs ("12.") and case citations ("v. SEBI").
"""

from __future__ import annotations

import re
from collections.abc import Iterator

from finpulse.core.offsets import Span

# Never end a sentence, whatever follows.
_NEVER = frozenset(
    (
        "mr mrs ms dr prof shri smt sh hon hon'ble m/s no nos sr jr rs re vs v viz sec secs reg regs art "
        "arts "
        "cl dy addl asst dept govt regn approx est fig para paras i.e e.g eg ie ref refs vol pp st nd rd th "
        "mt jan feb mar apr jun jul aug sep sept oct nov dec lt col gen capt maj"
    ).split()
)
# Often end a sentence, so they count as a boundary only when a sentence starter follows.
_MAYBE = frozenset("ltd pvt co corp inc ors anr etc llp plc".split())
_STARTERS = frozenset(
    (
        "the this that these those it its in on at as an he she they we you there thus hence however "
        "further accordingly pursuant after before upon vide whereas having considering since during "
        "for from by with under all any each both such our their his her what when where which who "
        "thereafter therefore moreover also now so if while although consequently noticee noticees"
    ).split()
)

_TERMINATOR = re.compile(r"""[.!?]+["'’)\]]*(?=\s)""")
_PARA_BREAK = re.compile(r"\n[ \t]*\n+")
_PREV_TOKEN = re.compile(r"([A-Za-z][A-Za-z./'’]*)\.*$")
_NEXT_WORD = re.compile(r"\s+([\"'(\[‘“]*)([A-Za-z0-9][\w'/&.-]*)")
_LIST_MARKER = re.compile(r"^\s*(?:\(?\d{1,3}|[ivxlc]{1,5})\.$")


def _is_boundary(para: str, seg_start: int, term: re.Match[str]) -> bool:
    nxt = _NEXT_WORD.match(para, term.end())
    if nxt is None:
        return para[term.end() :].strip() == ""
    opener, first = nxt.group(1), nxt.group(2)
    starter = first.lower() in _STARTERS
    before = para[seg_start : term.start()]

    if term.group(0).startswith("."):
        if _LIST_MARKER.match(before + "."):
            return False  # "12." opening a numbered paragraph
        tok = _PREV_TOKEN.search(before + ".")
        if tok:
            word = tok.group(1).rstrip(".").lower()
            if len(word) == 1 and word.isalpha():
                return starter  # an initial ("A. K. Gupta"), unless a sentence starter follows
            if word in _NEVER:
                return False
            if word in _MAYBE:
                return starter and not opener.startswith("(")
        if first[0].islower() and not opener:
            return False
    return first[0].isupper() or first[0].isdigit() or bool(opener)


def _paragraph_ranges(text: str) -> Iterator[tuple[int, int]]:
    start = 0
    for m in _PARA_BREAK.finditer(text):
        yield start, m.start()
        start = m.end()
    yield start, len(text)


def split_sentences(text: str) -> list[Span]:
    """Sentence spans in order, trimmed of whitespace, covering all non-blank text."""
    spans: list[Span] = []

    def emit(para: str, offset: int, start: int, end: int) -> None:
        seg = para[start:end]
        lead = len(seg) - len(seg.lstrip())
        trail = len(seg) - len(seg.rstrip())
        if end - trail > start + lead:
            spans.append(Span(offset + start + lead, offset + end - trail))

    for p_start, p_end in _paragraph_ranges(text):
        para = text[p_start:p_end]
        pos = 0
        for term in _TERMINATOR.finditer(para):
            if _is_boundary(para, pos, term):
                emit(para, p_start, pos, term.end())
                pos = term.end()
        emit(para, p_start, pos, len(para))
    return spans
