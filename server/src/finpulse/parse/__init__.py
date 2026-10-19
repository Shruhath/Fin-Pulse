from __future__ import annotations

from pathlib import Path

from .html import parse_html
from .ocr import OcrUnavailable, tesseract_version
from .pdf import ParsedDocument, ParsedPage, parse_pdf

__all__ = [
    "OcrUnavailable",
    "ParsedDocument",
    "ParsedPage",
    "parse_file",
    "parse_html",
    "parse_pdf",
    "tesseract_version",
]


def parse_file(path: Path, *, ocr: bool = True) -> ParsedDocument:
    """Parse a PDF, an HTML page or a plain-text file by its extension."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return parse_pdf(path, ocr=ocr)
    if suffix in {".html", ".htm"}:
        return parse_html(path.read_bytes())
    if suffix in {".txt", ".text"}:
        return ParsedDocument([ParsedPage(1, path.read_text(encoding="utf-8", errors="replace"), False)])
    raise ValueError(f"unsupported file type: {path.name}")
