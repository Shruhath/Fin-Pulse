import zipfile

import numpy as np
import pytest

from finpulse.eval.modelpapers import PUBLISHED_F, SoPmi, class_report, load_fpb, published_macro
from finpulse.sentiment.data import LABELS


def test_the_published_figures_average_to_the_macro_f1_reported_in_the_comparison():
    assert published_macro(PUBLISHED_F["HSC (model paper 1, as published)"]["DS50"]) == pytest.approx(
        0.763, abs=1e-3
    )
    assert published_macro(
        PUBLISHED_F["LPS (Malo et al., as published in model paper 1)"]["DS100"]
    ) == pytest.approx(0.803, abs=1e-3)


def test_phrasebank_levels_are_read_from_the_zip_and_a_bad_line_is_skipped(tmp_path):
    (tmp_path / "financial_phrasebank" / "data").mkdir(parents=True)
    path = tmp_path / "financial_phrasebank" / "data" / "FinancialPhraseBank-v1.0.zip"
    with zipfile.ZipFile(path, "w") as z:
        for name in ("AllAgree", "75Agree", "66Agree", "50Agree"):
            z.writestr(
                f"FinancialPhraseBank-v1.0/Sentences_{name}.txt",
                "Profit rose 5 % .@positive\nA line with no label\n"
                "Sales fell .@negative\nA board meeting .@neutral\n",
            )
    data = load_fpb(tmp_path)
    assert set(data) == {"DS100", "DS75", "DS66", "DS50"}
    assert data["DS100"] == [
        ("Profit rose 5 % .", "positive"),
        ("Sales fell .", "negative"),
        ("A board meeting .", "neutral"),
    ]


def test_class_report_gives_macro_precision_recall_f1_and_auc():
    gold = ["negative", "neutral", "positive", "positive"]
    probs = np.array(
        [[0.8, 0.1, 0.1], [0.1, 0.8, 0.1], [0.1, 0.1, 0.8], [0.1, 0.8, 0.1]]
    )  # one positive missed
    r = class_report(gold, probs)
    assert r["accuracy"] == 0.75 and r["n"] == 4.0
    assert r["precisionMacro"] == pytest.approx((1 + 0.5 + 1) / 3) and r["recallMacro"] == pytest.approx(
        (1 + 1 + 0.5) / 3
    )
    assert 0.5 < r["aucMacro"] <= 1.0 and set(LABELS) <= {
        k.removeprefix("f1_") for k in r if k.startswith("f1_")
    }


def test_so_pmi_scores_words_that_travel_with_positive_seeds_above_those_with_negative_seeds():
    titles = ["shares rise on strong profit and record order book"] * 4 + [
        "firm reports loss as sales fall and costs drop"
    ] * 4
    model = SoPmi(titles, min_df=2)
    assert model.score("order book") > 0 > model.score("sales costs")
    assert (
        SoPmi.label(0.2, 0.5) == "neutral"
        and SoPmi.label(0.9, 0.5) == "positive"
        and SoPmi.label(-0.9, 0.5) == "negative"
    )
