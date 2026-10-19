"""PDF text extraction with a per-page OCR fallback.

PyMuPDF reads the text layer. A page with too few words has no usable text layer (a scan),
so that page is rendered and sent through Tesseract; `ocr_used` records that it happened.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

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


def _text_layer(page: pymupdf.Page) -> str:
    blocks = page.get_text("blocks", sort=True)
    return "\n\n".join(b[4].strip() for b in blocks if b[6] == 0 and b[4].strip())


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
