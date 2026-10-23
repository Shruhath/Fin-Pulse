"""Main-content extraction for HTML pages (SEBI order pages, RBI press releases)."""

from __future__ import annotations

import trafilatura

from .pdf import ParsedDocument, ParsedPage


def parse_html(html: str | bytes) -> ParsedDocument:
    text = trafilatura.extract(html, include_comments=False, include_tables=True, favor_recall=True) or ""
    return ParsedDocument([ParsedPage(1, text, False)])
