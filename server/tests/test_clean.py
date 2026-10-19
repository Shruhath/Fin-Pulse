from finpulse.preprocess.clean import clean_pages, clean_text, fix_characters, strip_page_furniture


def test_fix_characters_repairs_mojibake_and_normalises():
    assert fix_characters("The noticeeâ€™s reply") == "The noticee's reply"
    assert fix_characters("ﬁled on 3 Mar") == "filed on 3 Mar"  # fi ligature
    assert fix_characters("a\r\nb\rc") == "a\nb\nc"


def test_soft_wraps_are_joined_and_paragraphs_kept():
    raw = "The Board met on\nMonday and approved\nthe deal.\n\nThe next item was\nthe dividend."
    assert (
        clean_text(raw) == "The Board met on Monday and approved the deal.\n\nThe next item was the dividend."
    )


def test_hyphenated_line_breaks_are_repaired_only_before_lowercase():
    assert clean_text("The compli-\nance officer resigned.") == "The compliance officer resigned."
    assert clean_text("See Section 11-\nB of the Act.") == "See Section 11- B of the Act."


def test_running_headers_footers_and_page_numbers_are_removed():
    pages = [
        "SECURITIES AND EXCHANGE BOARD OF INDIA\nOrder in the matter of X Ltd\n\n"
        f"Body text {n} goes here.\n\nPage {n} of 4"
        for n in range(1, 5)
    ]
    cleaned = clean_pages(pages)
    assert "SECURITIES AND EXCHANGE BOARD" not in cleaned
    assert "Page " not in cleaned
    assert cleaned.count("Body text") == 4


def test_furniture_needs_three_pages_to_be_recognised():
    pages = ["HEADER\nBody one.", "HEADER\nBody two."]
    assert "HEADER" in strip_page_furniture(pages)[0]


def test_body_lines_that_only_look_like_numbers_are_kept_in_the_middle():
    pages = ["Intro line.\n\nMiddle\n12\nsection text.\n\nOutro line."]
    assert "12" in clean_pages(pages)


def test_a_sentence_running_over_a_page_break_is_rejoined():
    pages = ["The Board resolved that the", "company shall repay the loan.\n\nNext paragraph."]
    assert (
        clean_pages(pages) == "The Board resolved that the company shall repay the loan.\n\nNext paragraph."
    )


def test_a_finished_sentence_before_a_page_break_is_not_joined():
    pages = ["The deal closed.", "the next page starts lowercase."]
    assert clean_pages(pages) == "The deal closed.\n\nthe next page starts lowercase."


def test_rupee_sign_and_indian_digits_survive_nfkc():
    assert "₹25,00,000" in clean_text("penalty of ₹25,00,000/-")


def test_empty_input():
    assert clean_text("") == ""
    assert clean_pages([]) == ""
