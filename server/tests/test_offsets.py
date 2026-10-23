import pytest

from finpulse.core.offsets import Span, check_against, drop_overlaps, locate_sentence


def test_span_rejects_inverted_ranges():
    with pytest.raises(ValueError):
        Span(5, 4)
    with pytest.raises(ValueError):
        Span(-1, 3)


def test_slice_and_check_round_trip():
    text = "Yes Bank was penalised."
    span = Span(0, 8)
    assert span.slice(text) == "Yes Bank"
    assert check_against(text, span, "Yes Bank")
    assert not check_against(text, span, "Yes bank")
    assert not check_against(text, Span(0, 999), "Yes Bank")


def test_overlap_is_half_open():
    assert not Span(0, 5).overlaps(Span(5, 9))
    assert Span(0, 6).overlaps(Span(5, 9))
    assert Span(0, 10).contains(Span(2, 4))


def test_drop_overlaps_keeps_the_longest_then_the_earliest():
    spans = [Span(0, 4), Span(0, 12), Span(20, 24), Span(22, 26)]
    assert drop_overlaps(spans) == [Span(0, 12), Span(20, 24)]


def test_locate_sentence_binary_search_and_gaps():
    sents = [Span(0, 10), Span(12, 20), Span(21, 30)]
    assert locate_sentence(sents, 0) == 0
    assert locate_sentence(sents, 9) == 0
    assert locate_sentence(sents, 10) is None  # the gap between sentences
    assert locate_sentence(sents, 25) == 2
    assert locate_sentence(sents, 30) is None
    assert locate_sentence([], 3) is None
