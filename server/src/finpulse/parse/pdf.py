"""PDF text extraction with a per-page OCR fallback.

PyMuPDF reads the text layer. A page with too few words has no usable text layer (a scan),
so that page is rendered and sent through Tesseract; `ocr_used` records that it happened.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import pairwise
from pathlib import Path
from statistics import median

import pymupdf

from finpulse.core.settings import get_settings

from .ocr import ocr_png


@dataclass(slots=True)
class ParsedPage:
    number: int  # 1-based
    text: str
    ocr: bool

    @property
    def words(self) -> int:
        return len(self.text.split())


@dataclass(slots=True)
class ParsedDocument:
    pages: list[ParsedPage] = field(default_factory=list)

    @property
    def ocr_used(self) -> bool:
        return any(p.ocr for p in self.pages)

    @property
    def page_texts(self) -> list[str]:
        return [p.text for p in self.pages]


_PARAGRAPH_GAP = 1.4  # a line pitch this many times the page's usual pitch starts a new paragraph


def _text_layer(page: pymupdf.Page) -> str:
    """The page's text with blank lines between paragraphs and single newlines between wrapped lines.

    Many filings come out of PyMuPDF with one text block per line, so blocks are not paragraphs.
    Paragraphs are rebuilt from the vertical distance between consecutive lines instead.
    """
    lines: list[tuple[float, str]] = []  # (top of line, text)
    for block in page.get_text("dict", sort=True)["blocks"]:
        if block["type"] != 0:
            continue
        for line in block["lines"]:
            text = "".join(span["text"] for span in line["spans"]).strip()
            if text:
                lines.append((line["bbox"][1], text))
    if not lines:
        return ""
    pitches = [b[0] - a[0] for a, b in pairwise(lines) if 2 < b[0] - a[0] < 60]
    typical = median(pitches) if pitches else 0.0
    paragraphs: list[list[str]] = [[lines[0][1]]]
    for (prev_top, _), (top, text) in pairwise(lines):
        pitch = top - prev_top
        if typical and pitch > typical * _PARAGRAPH_GAP:
            paragraphs.append([text])
        elif abs(pitch) <= 2:  # same baseline: a table cell or a split run, not a new line
            paragraphs[-1][-1] += " " + text
        else:
            paragraphs[-1].append(text)
    return "\n\n".join("\n".join(p) for p in paragraphs)


def parse_pdf(
    path: Path,
    *,
    ocr: bool = True,
    min_words_per_page: int | None = None,
    dpi: int | None = None,
) -> ParsedDocument:
    cfg = get_settings()
    min_words = cfg.ocr_min_words_per_page if min_words_per_page is None else min_words_per_page
    dpi = dpi or cfg.ocr_dpi
    doc = ParsedDocument()
    with pymupdf.open(path) as pdf:
        for i, page in enumerate(pdf, start=1):
            text = _text_layer(page)
            used_ocr = False
            if ocr and len(text.split()) < min_words:
                pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)
                recognised = ocr_png(pix.tobytes("png"))
                if len(recognised.split()) > len(text.split()):
                    text, used_ocr = recognised, True
            doc.pages.append(ParsedPage(i, text, used_ocr))
    return doc
