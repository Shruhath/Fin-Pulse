"""RBI press releases from the Reserve Bank's own RSS feed.

The feed is the publisher's machine-readable offering, so it is read as a feed (one request per run,
identifying User-Agent), not crawled; RBI's robots.txt sits behind a bot wall and cannot be read, so
no page other than the feed is ever fetched. The feed carries only the latest items, so the collector
is meant to run every day and the corpus grows by what it sees. Each item is stored once, keyed by a
hash of its text.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass

import httpx
from lxml import etree
from sqlalchemy import select
from sqlalchemy.orm import Session

from finpulse.db.models import Document, IngestFailure

from .fetch import USER_AGENT
from .rss import parse_feed

log = logging.getLogger(__name__)

FEED_URL = "https://rbi.org.in/pressreleases_rss.xml"


@dataclass(slots=True)
class RbiStats:
    seen: int = 0
    created: int = 0
    existing: int = 0
    empty: int = 0


def collect_rbi(session: Session, *, client: httpx.Client | None = None, url: str = FEED_URL) -> RbiStats:
    own = client is None
    client = client or httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=30.0, follow_redirects=True)
    stats = RbiStats()
    try:
        try:
            resp = client.get(url)
            resp.raise_for_status()
            items = parse_feed(resp.content)
        except (httpx.HTTPError, ValueError, etree.LxmlError) as exc:
            session.add(
                IngestFailure(
                    url=url,
                    source_kind="RBI",
                    failure_class=type(exc).__name__,
                    attempts=[{"error": str(exc)[:300]}],
                )
            )
            session.flush()
            raise
    finally:
        if own:
            client.close()

    known = set(session.scalars(select(Document.raw_sha256).where(Document.source_kind == "RBI")))
    for item in items:
        stats.seen += 1
        text = item.text
        if not text:
            stats.empty += 1
            continue
        sha = hashlib.sha256(f"{item.title}\n{text}".encode()).hexdigest()
        if sha in known:
            stats.existing += 1
            continue
        known.add(sha)
        session.add(
            Document(
                source_kind="RBI",
                url=item.link,
                title=item.title,
                doc_type="RBI press release",
                published_at=item.published,
                raw_sha256=sha,
                status="ingested",
                meta={"origin": "rss-rbi", "text": text, "feed": url},
            )
        )
        stats.created += 1
    session.flush()
    return stats
