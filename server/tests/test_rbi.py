# ruff: noqa: E501  (the feed fixture keeps the publisher's long lines)
from datetime import date
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import select

from finpulse.db.models import Document, IngestFailure
from finpulse.entities.titles import title_subjects
from finpulse.events.rules import extract_events
from finpulse.events.taxonomy import EventType
from finpulse.ingest.rbi import collect_rbi
from finpulse.ingest.rss import parse_feed
from finpulse.pipeline.parse import parse_pending
from finpulse.preprocess.sentences import split_sentences

FEED = """﻿<?xml version="1.0" encoding="utf-8"?><rss version="2.0"><channel><title>PRESS RELEASES FROM RBI</title>
<item><title><![CDATA[Directions under Section 35A read with Section 56 of the Banking Regulation Act, 1949 – The Konark Urban Co-operative Bank Ltd., Ulhasnagar]]></title>
<link>https://www.rbi.org.in/scripts/BS_PressReleaseDisplay.aspx?prid=63831</link>
<pubDate>Mon, 19 Oct 2026 17:30:00</pubDate>
<description><![CDATA[<table><tr><td><p>The Reserve Bank of India issued Directions under Section 35A read with Section 56 of the Banking Regulation Act, 1949 to The Konark Urban Co-operative Bank Ltd., Ulhasnagar. The directions are extended to October 2027.</p></td></tr></table>]]></description></item>
<item><title><![CDATA[Monetary Penalty on The Sample Co-operative Bank Ltd.]]></title>
<link>https://www.rbi.org.in/scripts/BS_PressReleaseDisplay.aspx?prid=63800</link>
<pubDate>Fri, 16 Oct 2026 12:00:00</pubDate>
<description><![CDATA[<p>The Reserve Bank of India has imposed a monetary penalty of ₹5.00 lakh on The Sample Co-operative Bank Ltd. in exercise of powers under Section 47A(1)(c) of the Banking Regulation Act, 1949.</p>]]></description></item>
<item><title><![CDATA[Money Market Operations as on October 18, 2026]]></title>
<link>https://www.rbi.org.in/scripts/BS_PressReleaseDisplay.aspx?prid=63820</link>
<pubDate>Sun, 18 Oct 2026 10:00:00</pubDate><description></description></item>
</channel></rss>"""


def _mock(body=FEED, status=200):
    return httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(status, text=body)))


def test_feed_items_are_parsed_with_dates_and_readable_text():
    items = parse_feed(FEED)
    assert [i.published for i in items] == [date(2026, 10, 19), date(2026, 10, 16), date(2026, 10, 18)]
    assert "Banking Regulation Act" in items[0].title
    assert items[0].text.startswith("The Reserve Bank of India issued Directions")
    assert "<p>" not in items[1].text and items[2].text == ""


def test_a_hostile_feed_does_not_expand_entities():
    bomb = (
        '<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaaaaaaaa"><!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;">]>'
        "<rss><channel><item><title>&b;</title><link>http://x.test/1</link></item></channel></rss>"
    )
    assert all("aaaaaaaaaa" not in item.title for item in parse_feed(bomb))


@pytest.mark.db
def test_collecting_stores_each_item_once_and_skips_empty_ones(db):
    first = collect_rbi(db, client=_mock())
    assert (first.seen, first.created, first.empty, first.existing) == (3, 2, 1, 0)
    again = collect_rbi(db, client=_mock())
    assert (again.created, again.existing) == (0, 2)
    doc = db.scalar(select(Document).where(Document.title.like("Monetary Penalty%")))
    assert doc.source_kind == "RBI" and doc.published_at == date(2026, 10, 16) and doc.status == "ingested"
    assert doc.meta["origin"] == "rss-rbi" and "monetary penalty" in doc.meta["text"]


@pytest.mark.db
def test_a_failed_fetch_goes_to_the_dead_letter_table(db):
    with pytest.raises(httpx.HTTPStatusError):
        collect_rbi(db, client=_mock("blocked", 418))
    failure = db.scalar(select(IngestFailure).where(IngestFailure.source_kind == "RBI"))
    assert failure.failure_class == "HTTPStatusError"


@pytest.mark.db
def test_text_documents_parse_without_a_file(db):
    collect_rbi(db, client=_mock())
    stats = parse_pending(db, workers=1)
    assert (stats.parsed, stats.failed) == (2, 0)
    doc = db.scalar(select(Document).where(Document.title.like("Monetary Penalty%")))
    assert doc.status == "parsed" and "Sample Co-operative Bank" in doc.clean_text


@pytest.mark.parametrize(
    ("title", "name"),
    [
        ("Monetary Penalty on The Sample Co-operative Bank Ltd.", "Sample Co-operative Bank Ltd"),
        ("Directions under Section 35A read with Section 56 of the Banking Regulation Act, 1949 – The Konark "
         "Urban Co-operative Bank Ltd., Ulhasnagar", "Konark Urban Co-operative Bank Ltd"),
        ("Cancellation of Certificate of Registration of XYZ Finance Limited", "XYZ Finance Limited"),
    ],
)  # fmt: skip
def test_rbi_titles_name_the_bank(title, name):
    (subject,) = title_subjects(title, "RBI")
    assert subject.name.rstrip(".") == name.rstrip(".") and subject.kind == "company"


def test_non_party_rbi_titles_yield_nothing():
    assert title_subjects("Money Market Operations as on October 18, 2026", "RBI") == []
    assert title_subjects("Auction of Government of India Dated Securities", "RBI") == []


def _events(text):
    return extract_events(
        source_kind="RBI", doc_type="RBI press release", text=text,
        sentence_spans=split_sentences(text), published_at=date(2026, 10, 16),
    )  # fmt: skip


def test_rbi_penalty_event_has_the_amount_and_the_provision():
    text = (
        "The Reserve Bank of India has imposed a monetary penalty of Rs. 5.00 lakh on The Sample Bank in "
        "exercise of powers under Section 47A(1)(c) of the Banking Regulation Act, 1949."
    )
    (ev,) = _events(text)
    assert ev.type is EventType.RBI_ACTION and ev.arguments["action"] == "monetary penalty"
    assert (
        ev.amount_inr == Decimal(500000)
        and "Section 47A(1)(c) of Banking Regulation Act, 1949" in ev.arguments["provisions"]
    )
    assert ev.schema_valid


def test_rbi_directions_and_cancellations_and_silence():
    (d,) = _events(
        "The Reserve Bank of India issued Directions under Section 35A of the Banking Regulation Act, 1949."
    )
    assert d.arguments["action"] == "directions" and d.amount_inr is None
    (c,) = _events(
        "The Reserve Bank of India has cancelled the licence of the Sample Bank to carry on banking business."
    )
    assert c.arguments["action"] == "licence cancelled"
    assert _events("The Reserve Bank conducted a 7-day Variable Rate Repo auction on Monday.") == []
