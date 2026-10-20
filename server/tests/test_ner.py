import json

import pytest

from finpulse.entities.names import tokenize
from finpulse.ner.data import NerData, load_ner_data, spans_from_tags, tags_from_spans
from finpulse.ner.metrics import span_scores

crfsuite = pytest.importorskip("sklearn_crfsuite")  # CI installs the ml extra and checks that it imports


def test_bio_tags_round_trip_through_spans():
    text = "Yes Bank and Tata Motors Ltd rose"
    tokens = tokenize(text)
    spans = {(0, 8), (13, 28)}
    tags = tags_from_spans(tokens, spans)
    assert tags == ["B-ORG", "I-ORG", "O", "B-ORG", "I-ORG", "I-ORG", "O"]
    assert spans_from_tags(tokens, tags) == spans
    assert spans_from_tags(tokens, ["I-ORG", "O", "O", "O", "O", "O", "O"]) == {
        (0, 3)
    }  # a stray I starts a span


def test_spans_that_cut_a_word_or_overlap_are_rejected():
    tokens = tokenize("Yes Bank rose")
    assert tags_from_spans(tokens, {(0, 6)}) is None  # ends inside "Bank"
    assert tags_from_spans(tokens, {(0, 8), (4, 8)}) is None  # overlapping


def test_scores_are_exact_span_matches():
    gold = [{(0, 3), (5, 9)}, set()]
    pred = [{(0, 3), (5, 8)}, {(1, 2)}]
    s = span_scores(gold, pred)
    assert s["spanPrecision"] == pytest.approx(1 / 3) and s["spanRecall"] == pytest.approx(1 / 2)
    assert s["spanF1"] == pytest.approx(0.4) and s["goldSpans"] == 2.0
    assert span_scores([set()], [set()])["spanF1"] == 0.0


def test_loading_builds_bio_sentences_from_both_datasets_and_counts_drops(tmp_path):
    (tmp_path / "finentity").mkdir()
    (tmp_path / "finentity" / "FinEntity.json").write_text(
        json.dumps(
            [
                {
                    "content": "Chevron and Halliburton rose.",
                    "annotations": [
                        {"start": 0, "end": 7, "tag": "Positive", "value": "Chevron"},
                        {"start": 12, "end": 23, "tag": "Neutral", "value": "Halliburton"},
                    ],
                },
                {
                    "content": "Chevron-based firm fell.",
                    "annotations": [{"start": 0, "end": 5, "tag": "Negative", "value": "Chevr"}],
                },
            ]
        )
    )
    (tmp_path / "sentfin").mkdir()
    (tmp_path / "sentfin" / "SEntFiN.csv").write_text(
        "S No.,Title,Decisions,Words\n1,MMTC Q2 net loss at Rs 10.4 crore,\"{'MMTC': 'negative'}\",8\n"
    )
    data = load_ner_data(tmp_path)
    assert isinstance(data, NerData)
    by_text = {s.text: s for s in data.sentences}
    assert by_text["Chevron and Halliburton rose."].tags == ["B-ORG", "O", "B-ORG", "O"]
    assert by_text["MMTC Q2 net loss at Rs 10.4 crore"].spans() == {(0, 4)}
    assert data.dropped["span not on token boundaries"] == 1  # "Chevr" cuts a word
    assert {s.dataset for s in data.sentences} == {"FinEntity", "SEntFiN"}


def _toy_sentences():
    from finpulse.ner.data import Sentence

    names = [
        "Alpha Bank Ltd",
        "Beta Steel Limited",
        "Gamma Motors",
        "Delta Pharma Ltd",
        "Omega Textiles Limited",
    ]
    frames = [
        "{} reported strong quarterly results",
        "shares of {} fell on Monday",
        "SEBI penalised {} for delays",
    ]
    out = []
    for i in range(60):
        name = names[i % len(names)].replace("Alpha", f"Alpha{i % 7}")
        text = frames[i % len(frames)].format(name)
        tokens = tokenize(text)
        at = text.index(name)
        out.append(Sentence(text, tokens, tags_from_spans(tokens, {(at, at + len(name))}), "train", "toy"))
    return out


def test_the_crf_learns_company_names_and_reports_span_probabilities():
    from finpulse.ner.crf import CrfNer

    sentences = _toy_sentences()
    crf = CrfNer(["Alpha Bank Ltd", "Beta Steel Limited"]).fit([(s.tokens, s.tags) for s in sentences[:48]])
    gold = [s.spans() for s in sentences[48:]]
    pred = [{(a, b) for a, b, _ in crf.predict_spans(s.text)} for s in sentences[48:]]
    assert span_scores(gold, pred)["spanF1"] > 0.8
    (span,) = crf.predict_spans("shares of Beta Steel Limited fell on Monday")
    assert span[:2] == (10, 28) and 0.5 < span[2] <= 1.0
    assert crf.predict_spans("") == [] and crf.version.startswith("crf-gazetteer@")
    assert crf.predict_batch(["a", "b"]) == [[], []] or len(crf.predict_batch(["a", "b"])) == 2


def test_the_crf_round_trips_through_disk(tmp_path):
    from finpulse.ner.crf import CrfNer

    sentences = _toy_sentences()
    crf = CrfNer().fit([(s.tokens, s.tags) for s in sentences])
    loaded = CrfNer.load(crf.save(tmp_path))
    text = "shares of Omega Textiles Limited fell"
    assert loaded.predict_spans(text) == crf.predict_spans(text) and loaded.version == crf.version


@pytest.mark.db
def test_the_ner_stage_adds_unlisted_names_links_the_known_ones_and_skips_overlaps(db):
    from sqlalchemy import select

    from finpulse.db.models import Document, Entity, EntityAlias, Mention, Sentence
    from finpulse.pipeline.ner import ner_pending
    from finpulse.preprocess.sentences import split_sentences

    text = (
        "Beta Steel Limited and Zeta Foods Limited were examined by the Board. "
        "Low Confidence Co was also named."
    )
    doc = Document(source_kind="SEBI", title="Order", raw_sha256="a" * 64, clean_text=text, status="parsed")
    db.add(doc)
    db.flush()
    for i, sp in enumerate(split_sentences(text)):
        db.add(Sentence(doc_id=doc.id, idx=i, char_start=sp.start, char_end=sp.end, text=sp.slice(text)))
    beta = Entity(slug="beta-steel", canonical_name="Beta Steel Limited")
    db.add(beta)
    db.flush()
    db.add(EntityAlias(entity_id=beta.id, alias="Beta Steel Limited", alias_norm="beta steel", origin="nse"))
    db.add(
        Mention(
            doc_id=doc.id,
            entity_id=beta.id,
            char_start=0,
            char_end=18,
            surface="Beta Steel Limited",
            ner_model="gz",
        )
    )
    db.flush()

    NAMES = (
        ("Beta Steel Limited", 0.99),
        ("Zeta Foods Limited", 0.95),
        ("Low Confidence Co", 0.3),
    )

    class Model:
        version = "fake-ner@1"

        def predict_batch(self, texts):
            out = []
            for t in texts:
                found = []
                for name, score in NAMES:
                    if name in t:
                        found.append((t.index(name), t.index(name) + len(name), score))
                out.append(found)
            return out

    stats = ner_pending(db, Model())
    assert (stats.mentions, stats.linked) == (
        1,
        0,
    )  # Beta overlaps an existing mention; the low score is dropped
    zeta = db.scalar(select(Mention).where(Mention.ner_model == "fake-ner@1"))
    assert (
        zeta.surface == "Zeta Foods Limited" and zeta.entity_id is None and zeta.link_method == "unresolved"
    )
    assert text[zeta.char_start : zeta.char_end] == zeta.surface
    assert ner_pending(db, Model()).mentions == 0  # already processed by this model version
