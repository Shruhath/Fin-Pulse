from datetime import date
from decimal import Decimal

import pytest

from finpulse.preprocess.normalize import (
    find_amounts,
    find_dates,
    find_identifiers,
    find_statutes,
    format_inr,
    isin_valid,
    mask_pan,
)


@pytest.mark.parametrize(
    ("text", "inr"),
    [
        ("penalty of Rs. 25,00,000/- imposed", "2500000"),
        ("penalty of Rs.5 lakh", "500000"),
        ("a fine of ₹ 1,200 crore", "12000000000"),
        ("MMTC Q2 net loss at Rs 10.4 crore", "104000000"),
        ("INR 2.5 Cr. was paid", "25000000"),
        ("a package of Rs. 1.5 lakh crore", "1500000000000"),
        ("Rs. 3,50,000 and more", "350000"),
        ("Rs 2,500,000 western grouping", "2500000"),
        ("Rupees 40 lakhs", "4000000"),
        ("INR 12 million", "12000000"),
        ("Rs. 4 bn", "4000000000"),
    ],
)
def test_amounts_normalise_to_exact_inr(text, inr):
    found = find_amounts(text)
    assert [a.inr for a in found] == [Decimal(inr)]


def test_amount_span_slices_the_surface_without_the_sentence_dot():
    text = "The noticee paid Rs. 5 crore. Next sentence."
    (a,) = find_amounts(text)
    assert a.span.slice(text) == a.surface == "Rs. 5 crore"


def test_amounts_need_a_currency_marker():
    assert find_amounts("SpiceJet to issue 6.4 crore warrants to promoters") == []
    assert find_amounts("Rupees Twenty Five Lakh only") == []


def test_spelled_out_amount_in_brackets_is_not_double_counted():
    found = find_amounts("Rs. 25,00,000/- (Rupees Twenty Five Lakh only)")
    assert [a.inr for a in found] == [Decimal(2500000)]


def test_several_amounts_keep_text_order():
    found = find_amounts("fine of Rs. 10 lakh and costs of Rs. 2 lakh")
    assert [a.inr for a in found] == [Decimal(1000000), Decimal(200000)]


@pytest.mark.parametrize(
    ("value", "words"),
    [
        (Decimal(25000000), "₹2.5 crore"),
        (Decimal(500000), "₹5 lakh"),
        (Decimal("1.5e12"), "₹1.5 lakh crore"),
        (Decimal(9500), "₹9500"),
    ],
)
def test_format_inr_uses_indian_units(value, words):
    assert format_inr(value) == words


@pytest.mark.parametrize(
    ("text", "iso"),
    [
        ("order dated 12/03/2023 stands", date(2023, 3, 12)),
        ("on 05-11-2021,", date(2021, 11, 5)),
        ("on 7.8.2019.", date(2019, 8, 7)),
        ("on 12th March, 2023 the Board", date(2023, 3, 12)),
        ("12 March 2023", date(2023, 3, 12)),
        ("1-Apr-2020", date(2020, 4, 1)),
        ("March 12, 2023", date(2023, 3, 12)),
        ("Sept. 3 2024", date(2024, 9, 3)),
    ],
)
def test_dates_parse_day_first(text, iso):
    (d,) = find_dates(text)
    assert d.value == iso


def test_numeric_dates_are_never_guessed():
    assert find_dates("13/13/2023") == []
    assert find_dates("31/02/2023") == []
    assert find_dates("Quarter ended March 2023") == []


def test_date_span_slices_cleanly():
    text = "Order dated 12th March, 2023 was served."
    (d,) = find_dates(text)
    assert d.span.slice(text) == "12th March, 2023"


def test_isin_check_digit():
    assert isin_valid("INE002A01018")  # Reliance Industries
    assert isin_valid("INE040A01034")  # HDFC Bank
    assert not isin_valid("INE002A01019")
    assert not isin_valid("INE002A0101")


def test_identifiers():
    text = (
        "Reliance (ISIN INE002A01018, CIN L17110MH1973PLC019786) PAN ABCDE1234F, "
        "BSE Scrip Code: 500325, bad ISIN INE002A01019."
    )
    got = {(i.kind, i.value) for i in find_identifiers(text)}
    assert got == {
        ("isin", "INE002A01018"),
        ("cin", "L17110MH1973PLC019786"),
        ("pan", "ABCDE1234F"),
        ("bse_scrip", "500325"),
    }


def test_mask_pan_keeps_length_so_offsets_survive():
    text = "Noticee ABCDE1234F paid."
    masked = mask_pan(text)
    assert masked == "Noticee XXXXXXXXXX paid."
    assert len(masked) == len(text)


def test_statute_references():
    text = (
        "violated Section 11B of the SEBI Act, 1992 and Regulation 4(2)(a) of the "
        "PFUTP Regulations, 2003, besides section 7 of the Insolvency and Bankruptcy Code, 2016."
    )
    got = [(s.provision, s.instrument) for s in find_statutes(text)]
    assert ("Section 11B", "SEBI Act, 1992") in got
    assert ("Regulation 4(2)(a)", "PFUTP Regulations, 2003") in got
    assert ("section 7", "Insolvency and Bankruptcy Code, 2016") in got
