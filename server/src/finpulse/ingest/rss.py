"""RSS 2.0 reading, hardened for feeds we do not control (no entity expansion, no network access)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from email.utils import parsedate_to_datetime

from lxml import etree
from lxml import html as lxml_html


@dataclass(frozen=True, slots=True)
class FeedItem:
    title: str
    link: str
    published: date | None
    html: str

    @property
    def text(self) -> str:
        """Readable text of the item body, paragraphs separated by blank lines."""
        body = re.sub(r"(?i)</(p|tr|div|li|h\d)>|<br\s*/?>", "\n\n", self.html)
        try:
            text = lxml_html.fragment_fromstring(body, create_parent="div").text_content()
        except etree.ParserError:  # an empty description
            return ""
        paragraphs = (re.sub(r"[ \t\u00a0]+", " ", p).strip() for p in re.split(r"\n\s*\n", text))
        return "\n\n".join(p for p in paragraphs if p)


def _published(raw: str | None) -> date | None:
    if not raw:
        return None
    try:
        parsed: datetime = parsedate_to_datetime(raw.strip())
    except (TypeError, ValueError):
        return None
    return parsed.date()


def _field(item: etree._Element, name: str) -> str:
    node = item.find(name)
    return (node.text or "").strip() if node is not None and node.text else ""


def parse_feed(xml: str | bytes) -> list[FeedItem]:
    parser = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False, recover=False)
    root = etree.fromstring(xml.lstrip() if isinstance(xml, bytes) else xml.lstrip().encode("utf-8"), parser)
    items = []
    for item in root.iter("item"):
        title, link = _field(item, "title"), _field(item, "link")
        if title and link:
            items.append(
                FeedItem(title, link, _published(_field(item, "pubDate")), _field(item, "description"))
            )
    return items
