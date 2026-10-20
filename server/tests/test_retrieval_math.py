import numpy as np
import pytest

from finpulse.sentiment.calibration import fit_temperature, nll, softmax
from finpulse.sentiment.metrics import mcnemar
from finpulse.verify.bm25 import BM25, rrf, tokens

DOCS = [
    "SEBI imposed a penalty of Rs. 4,00,000 on the stock broker.",
    "The hearing was adjourned to the following month.",
    "The penalty was imposed under section 15HB of the SEBI Act.",
    "Mumbai recorded heavy rain during the week.",
]


def test_tokens_drop_stop_words_and_keep_numbers():
    assert tokens("The penalty of 4,00,000 under Section 15HB") == [
        "penalty",
        "4",
        "00",
        "000",
        "under",
        "section",
        "15hb",
    ]


def test_bm25_ranks_the_matching_sentences_first():
    bm = BM25(DOCS)
    assert bm.rank("penalty imposed on the broker", k=3) == [0, 2]
    assert bm.rank("section 15HB") == [2]
    assert bm.rank("quantum chromodynamics") == []  # nothing matches: no arbitrary results


def test_bm25_prefers_rarer_terms_and_handles_empty_input():
    bm = BM25(["alpha beta", "alpha gamma", "alpha delta"])
    scores = bm.scores("alpha beta")
    assert scores[0] > scores[1]
    assert BM25([]).rank("anything") == []


def test_rrf_rewards_agreement_between_rankings():
    fused = rrf([[1, 2, 3], [3, 1, 4]], k=60)
    assert [item for item, _ in fused][:2] == [1, 3]
    assert dict(fused)[1] == pytest.approx(1 / 61 + 1 / 62)
    assert rrf([]) == [] and rrf([[], []]) == []


def test_temperature_scaling_softens_an_overconfident_model():
    rng = np.random.default_rng(0)
    labels = rng.integers(0, 3, 600)
    logits = rng.normal(0, 1, (600, 3))
    logits[np.arange(600), labels] += 2.0
    flip = rng.random(600) < 0.35  # 35% of the confident predictions are wrong
    logits[flip] = np.roll(logits[flip], 1, axis=1)
    logits *= 4  # overconfident
    t = fit_temperature(logits, labels)
    assert t > 1.5
    assert nll(logits, labels, t) < nll(logits, labels, 1.0)
    assert softmax(logits, t).max(axis=1).mean() < softmax(logits).max(axis=1).mean()
    assert fit_temperature(np.zeros((0, 3)), np.zeros(0, dtype=int)) == 1.0


def test_mcnemar_counts_discordant_pairs_and_its_p_value():
    gold = ["p"] * 20
    a = ["p"] * 20  # always right
    b = ["n"] * 12 + ["p"] * 8  # wrong on 12
    r = mcnemar(gold, a, b)
    assert (r["a_only"], r["b_only"]) == (12.0, 0.0) and r["p_value"] < 0.01
    same = mcnemar(gold, a, a)
    assert same["p_value"] == 1.0
