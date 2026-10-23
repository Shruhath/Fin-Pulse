import json

import pytest

from finpulse.sentiment.baseline import PLACEHOLDER, SentimentBaseline, window_text
from finpulse.sentiment.data import (
    Example,
    load_finentity,
    load_sentfin,
    parse_decisions,
    split_of,
)
from finpulse.sentiment.metrics import confusion, f1_scores, reliability


def test_split_is_deterministic_and_roughly_80_10_10():
    splits = [split_of(f"sentence {i}") for i in range(4000)]
    assert splits == [split_of(f"sentence {i}") for i in range(4000)]
    share = {s: splits.count(s) / len(splits) for s in ("train", "dev", "test")}
    assert 0.77 < share["train"] < 0.83
    assert 0.07 < share["dev"] < 0.13 and 0.07 < share["test"] < 0.13


def test_window_replaces_the_entity_and_keeps_ten_words_each_side():
    words = [f"w{i}" for i in range(30)]
    text = " ".join(words[:15]) + " Yes Bank " + " ".join(words[15:])
    start = text.index("Yes Bank")
    window = window_text(text, start, start + len("Yes Bank"))
    parts = window.split()
    assert parts[10] == PLACEHOLDER
    assert parts[:10] == words[5:15] and parts[11:] == words[15:25]
    assert "Yes" not in parts and "Bank" not in parts


def test_window_at_the_edges_of_the_text():
    assert window_text("Yes Bank fell.", 0, 8) == f"{PLACEHOLDER} fell."


def test_sentfin_decisions_survive_apostrophes_in_names():
    raw = "{'Sebi': 'neutral', 'Osian's Art Fund': 'negative', 'Tata Motors': 'positive'}"
    assert parse_decisions(raw) == {
        "Sebi": "neutral",
        "Osian's Art Fund": "negative",
        "Tata Motors": "positive",
    }
    assert parse_decisions("{}") == {}


def test_loaders_locate_entities_and_report_drops(tmp_path):
    (tmp_path / "finentity").mkdir()
    (tmp_path / "finentity" / "FinEntity.json").write_text(
        json.dumps(
            [
                {
                    "content": "Chevron and Baker Hughes rose.",
                    "annotations": [
                        {
                            "start": 2,
                            "end": 9,
                            "tag": "Positive",
                            "value": "Chevron",
                            "label": "Positive",
                        },  # shifted
                        {
                            "start": 13,
                            "end": 25,
                            "tag": "Neutral",
                            "value": "Baker Hughes",
                            "label": "Neutral",
                        },
                        {"start": 0, "end": 4, "tag": "Negative", "value": "Nobody", "label": "Negative"},
                    ],
                }
            ]
        )
    )
    fin = load_finentity(tmp_path)
    assert [(e.surface, e.label) for e in fin.examples] == [
        ("Chevron", "positive"),
        ("Baker Hughes", "neutral"),
    ]
    assert fin.dropped["unlocatable"] == 1

    (tmp_path / "sentfin").mkdir()
    (tmp_path / "sentfin" / "SEntFiN.csv").write_text(
        "S No.,Title,Decisions,Words\n"
        "1,MMTC Q2 net loss at Rs 10.4 crore,\"{'MMTC': 'negative'}\",8\n"
        "2,Something else,\"{'Absent Co': 'positive'}\",2\n"
    )
    sent = load_sentfin(tmp_path)
    assert [(e.surface, e.label) for e in sent.examples] == [("MMTC", "negative")]
    assert sent.dropped["entity not in title"] == 1


def _examples():
    pos = [
        "{} jumped after record profit and strong order wins",
        "{} surged on upbeat guidance and a dividend hike",
    ]
    neg = [
        "{} slumped after fraud probe and heavy penalty",
        "{} plunged on weak results and a rating downgrade",
    ]
    neu = [
        "{} announced a board meeting date for next week",
        "{} appointed a new company secretary on Monday",
    ]
    out = []
    for i in range(40):
        for label, templates in (("positive", pos), ("negative", neg), ("neutral", neu)):
            text = templates[i % 2].format(f"Firm{i}")
            out.append(Example(text, 0, len(f"Firm{i}"), label, "toy", "train"))
    return out


def test_baseline_learns_a_toy_task_and_returns_ordered_probabilities():
    ex = _examples()
    windows = [window_text(e.text, e.start, e.end) for e in ex]
    model = SentimentBaseline().fit(windows, [e.label for e in ex])
    probe = [
        window_text("Acme surged on record profit and strong order wins", 0, 4),
        window_text("Acme slumped after a fraud probe and heavy penalty", 0, 4),
    ]
    assert model.predict(probe) == ["positive", "negative"]
    p = model.predict_proba(probe)
    assert p.shape == (2, 3)
    assert p.sum(axis=1) == pytest.approx([1.0, 1.0])
    assert p[0].argmax() == 2 and p[1].argmax() == 0  # columns are negative, neutral, positive
    assert model.version.startswith("tfidf-lr@")


def test_model_round_trips_through_disk(tmp_path):
    ex = _examples()
    model = SentimentBaseline().fit([window_text(e.text, e.start, e.end) for e in ex], [e.label for e in ex])
    loaded = SentimentBaseline.load(model.save(tmp_path))
    probe = [window_text("Acme surged on record profit", 0, 4)]
    assert loaded.version == model.version
    assert loaded.predict_proba(probe).tolist() == model.predict_proba(probe).tolist()


def test_metrics():
    gold = ["positive", "negative", "neutral", "neutral", "positive"]
    pred = ["positive", "negative", "neutral", "positive", "positive"]
    cm = confusion(gold, pred)
    assert cm == [[1, 0, 0], [0, 1, 1], [0, 0, 2]]  # rows gold, columns predicted
    scores = f1_scores(cm)
    assert scores["accuracy"] == pytest.approx(0.8)
    assert 0 < scores["macroF1"] < 1

    bins, ece = reliability([0.9, 0.9, 0.9, 0.9], [True, True, True, False])
    assert ece == pytest.approx(abs(0.75 - 0.9))
    assert bins[0]["n"] == 4
    assert reliability([1.0, 1.0], [True, True])[1] == 0.0
