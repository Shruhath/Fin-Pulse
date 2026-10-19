import numpy as np

from finpulse.summarize.prune import lead_n, lexrank, select, usable

CENTRAL = [
    "SEBI imposed a monetary penalty on Yes Bank for violating disclosure norms in its filings.",
    "The penalty on Yes Bank followed an inquiry into the disclosure norms and the filings it made.",
    "Disclosure norms require Yes Bank to report filings accurately, and the inquiry found violations.",
]
OUTLIER = "The weather in Mumbai was humid throughout the week of the hearing in the old building."


def test_usable_rejects_fragments_tables_and_furniture():
    assert usable("The Adjudicating Officer imposed a penalty on the Noticee under section 15HB.")
    assert not usable("Page 3")
    assert not usable("Sd/-")
    assert not usable("1,00,000 2,00,000 3,00,000 4,00,000 5,00,000 6,00,000")  # a table row
    assert not usable("Short one.")


def test_lexrank_prefers_the_sentence_the_others_resemble():
    scores = lexrank([*CENTRAL, OUTLIER])
    assert scores.sum() == np.float64(1.0) or abs(scores.sum() - 1.0) < 1e-9
    assert scores.argmin() == 3  # the outlier is the least central
    assert lexrank([]).size == 0 and lexrank(["only one"]).tolist() == [1.0]


def test_select_respects_the_budget_and_keeps_document_order():
    sents = [*CENTRAL, OUTLIER]
    chosen = select(sents, budget_chars=sum(len(s) + 8 for s in CENTRAL), must_keep=[])
    assert chosen == sorted(chosen)
    assert 3 not in chosen  # the outlier loses when space is short
    assert sum(len(sents[i]) + 8 for i in chosen) <= sum(len(s) + 8 for s in CENTRAL)


def test_must_keep_sentences_are_always_included_even_if_unusable():
    sents = [*CENTRAL, "Sd/-"]
    assert 3 in select(sents, budget_chars=10_000, must_keep=[3])
    assert select(sents, budget_chars=10_000, must_keep=[99]) == [0, 1, 2]  # out of range is ignored


def test_lead_n_skips_unusable_openers():
    sents = ["Page 1", "Sd/-", *CENTRAL, OUTLIER]
    assert lead_n(sents, 3) == [2, 3, 4]
