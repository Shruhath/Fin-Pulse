import numpy as np
import pytest

torch = pytest.importorskip("torch")  # CI installs the neural extra and checks that torch imports

from finpulse.embed.encoder import Embedder  # noqa: E402
from finpulse.sentiment.data import LABELS, Example  # noqa: E402
from finpulse.sentiment.finbert import MARK_CLOSE, MARK_OPEN, FinBert, marked, sentence_only  # noqa: E402
from finpulse.verify.nli import Nli  # noqa: E402
from tests import tiny  # noqa: E402

PROSUS = {0: "positive", 1: "negative", 2: "neutral"}  # the order ProsusAI/finbert uses


def test_marked_wraps_the_mention_and_keeps_forty_words_each_side():
    words = [f"w{i}" for i in range(100)]
    text = " ".join(words[:50]) + " Yes Bank " + " ".join(words[50:])
    start = text.index("Yes Bank")
    out = marked(text, start, start + 8).split()
    assert out[40:44] == [MARK_OPEN, "Yes", "Bank", MARK_CLOSE]
    assert out[:40] == words[10:50] and out[44:] == words[50:90]
    assert sentence_only(text, start, start + 8).split()[:3] == ["w0", "w1", "w2"]


def test_the_pretrained_head_is_reordered_to_negative_neutral_positive(tmp_path):
    directory = tiny.classifier(tmp_path / "fb", PROSUS)
    from transformers import AutoModelForSequenceClassification

    raw = AutoModelForSequenceClassification.from_pretrained(directory)
    with torch.no_grad():
        for row, value in enumerate((1.0, 2.0, 3.0)):  # positive, negative, neutral
            raw.classifier.weight[row].fill_(value)
            raw.classifier.bias[row] = value
    raw.save_pretrained(directory)
    model = FinBert.from_base(str(directory), device="cpu")
    weights = model.model.classifier.weight[:, 0].tolist()
    assert weights == [2.0, 3.0, 1.0]  # negative, neutral, positive
    assert dict(model.model.config.id2label) == dict(enumerate(LABELS))
    assert MARK_OPEN in model.tokenizer.get_vocab() and MARK_CLOSE in model.tokenizer.get_vocab()


def test_probabilities_sum_to_one_and_do_not_depend_on_batch_composition(tmp_path):
    model = FinBert.from_base(str(tiny.classifier(tmp_path / "fb", PROSUS)), device="cpu")
    items = [
        ("Yes Bank fell sharply today", 0, 8),
        ("a much longer sentence about Tata Motors results", 28, 39),
        ("Axis", 0, 4),
    ]
    together = model.predict_spans(items)
    assert together.shape == (3, 3) and together.sum(axis=1) == pytest.approx([1, 1, 1], abs=1e-5)
    alone = np.vstack([model.predict_spans([it]) for it in items])
    assert alone == pytest.approx(together, abs=1e-4)  # padding and length-sorting do not change answers


def _toy(n=40):
    pos = ["{} jumped on record profit and strong order wins", "{} surged after a dividend hike"]
    neg = ["{} slumped after fraud probe and penalty", "{} plunged on weak results and downgrade"]
    neu = ["{} announced a board meeting date", "{} appointed a company secretary"]
    out = []
    for i in range(n):
        for label, group in (("positive", pos), ("negative", neg), ("neutral", neu)):
            name = f"firm{i}"
            out.append(Example(group[i % 2].format(name), 0, len(name), label, "toy", "train"))
    return out


def test_fine_tuning_learns_a_separable_task_calibrates_and_round_trips(tmp_path):
    model = FinBert.from_base(str(tiny.classifier(tmp_path / "fb", PROSUS)), device="cpu")
    data = _toy()
    report = model.fit(data[:90], data[90:], epochs=20, lr=3e-3, batch_size=16)
    assert report.best_epoch >= 1 and report.epochs[-1]["train_loss"] < report.epochs[0]["train_loss"]
    assert report.epochs[report.best_epoch - 1]["dev_macro_f1"] > 0.7  # chance is about 0.33
    assert model.temperature > 0 and model.version.startswith("finbert-entity@")

    saved = model.save(tmp_path / "saved")
    loaded = FinBert.load(saved, device="cpu")
    probe = [
        ("firm9 jumped on record profit and strong order wins", 0, 5),
        ("firm9 slumped after fraud probe and penalty", 0, 5),
    ]
    assert loaded.version == model.version and loaded.temperature == pytest.approx(model.temperature)
    assert loaded.predict_spans(probe) == pytest.approx(model.predict_spans(probe), abs=1e-5)
    assert loaded.predict_spans(probe).argmax(axis=1).tolist() == [
        LABELS.index("positive"),
        LABELS.index("negative"),
    ]


def test_an_off_the_shelf_model_without_markers_ignores_the_mention(tmp_path):
    model = FinBert.from_base(
        str(tiny.classifier(tmp_path / "fb", PROSUS)), device="cpu", entity_marked=False
    )
    a = model.predict_spans([("Yes Bank and Tata both rose", 0, 8)])
    b = model.predict_spans([("Yes Bank and Tata both rose", 13, 17)])
    assert a == pytest.approx(b)  # the same sentence gives the same answer: no entity awareness


def test_embeddings_are_unit_length_and_keep_input_order(tmp_path):
    emb = Embedder(str(tiny.encoder(tmp_path / "enc")), device="cpu", batch_size=2)
    texts = ["penalty imposed on the broker", "a", "hearing adjourned to next month by the officer"]
    vecs = emb.encode(texts)
    assert vecs.shape == (3, 32) and np.linalg.norm(vecs, axis=1) == pytest.approx([1, 1, 1], abs=1e-5)
    assert emb.encode([texts[2]])[0] == pytest.approx(vecs[2], abs=1e-4)


def test_nli_maps_the_models_own_label_names_to_entail_neutral_contradict(tmp_path):
    directory = tiny.classifier(tmp_path / "nli", {0: "contradiction", 1: "entailment", 2: "neutral"})
    from transformers import AutoModelForSequenceClassification

    raw = AutoModelForSequenceClassification.from_pretrained(directory)
    with torch.no_grad():
        raw.classifier.weight.zero_()
        raw.classifier.bias.copy_(torch.tensor([0.0, 10.0, 0.0]))  # strongly "entailment" (column 1)
    raw.save_pretrained(directory)
    probs = Nli(str(directory), device="cpu").predict([("the fine was four lakh", "the fine was four lakh")])
    assert probs[0].argmax() == 0 and probs[0, 0] > 0.99  # reported as the first column: entailment
    assert probs.sum() == pytest.approx(1.0, abs=1e-5)
