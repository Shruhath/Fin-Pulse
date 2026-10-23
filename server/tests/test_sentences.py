from itertools import pairwise

import pytest

from finpulse.preprocess.sentences import split_sentences


def sents(text: str) -> list[str]:
    return [s.slice(text) for s in split_sentences(text)]


def test_plain_sentences():
    assert sents("Yes Bank was penalised. The order is final.") == [
        "Yes Bank was penalised.",
        "The order is final.",
    ]


def test_spans_slice_back_to_the_sentence():
    text = "First one.  Second one!\n\nThird one?"
    spans = split_sentences(text)
    assert [s.slice(text) for s in spans] == ["First one.", "Second one!", "Third one?"]
    assert spans[2].start == text.index("Third")


@pytest.mark.parametrize(
    "text",
    [
        "The penalty of Rs. 25 lakh was imposed on Mr. A. K. Gupta by the AO.",
        "Order against M/s Sintex Industries Ltd. and others was passed.",
        "Shri V. Kumar, Director, was heard on 12.03.2023 in the matter.",
        "See Reg. 4(2) read with Sec. 15HA of the Act.",
        "Notice No. 45 of 2022 was served.",
        "Rs.57.90 per share was the price on 3/6/2004.",
    ],
)
def test_abbreviations_do_not_split(text):
    assert sents(text) == [text]


def test_company_suffix_splits_only_before_a_sentence_starter():
    assert sents("The order was issued to Axis Bank Ltd. The bank replied.") == [
        "The order was issued to Axis Bank Ltd.",
        "The bank replied.",
    ]
    assert sents("The order against Axis Bank Ltd. Mumbai was passed.") == [
        "The order against Axis Bank Ltd. Mumbai was passed."
    ]


def test_numbered_paragraph_markers_stay_with_their_sentence():
    text = "1. The Board met on Monday.\n\n2. It approved the deal."
    assert sents(text) == ["1. The Board met on Monday.", "2. It approved the deal."]


def test_a_lowercase_continuation_is_not_a_boundary():
    assert sents("The ratio was 1.5 i.e. high, and e.g. rising.") == [
        "The ratio was 1.5 i.e. high, and e.g. rising."
    ]


def test_trailing_single_letter_before_a_starter_is_a_boundary():
    assert sents("Details are in Part A. The Board then met.") == [
        "Details are in Part A.",
        "The Board then met.",
    ]


def test_quoted_sentence_end():
    assert sents('He said "no further action." The matter ended.') == [
        'He said "no further action."',
        "The matter ended.",
    ]


def test_blank_and_whitespace_text():
    assert split_sentences("") == []
    assert split_sentences("  \n\n  ") == []


def test_every_span_is_inside_the_text_and_ordered():
    text = "Alpha beta. Gamma delta.\n\nEpsilon. Zeta?"
    spans = split_sentences(text)
    assert all(0 <= s.start < s.end <= len(text) for s in spans)
    assert all(a.end <= b.start for a, b in pairwise(spans))
