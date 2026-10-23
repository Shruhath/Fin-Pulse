import hashlib
import json

import pytest

pq = pytest.importorskip("pyarrow.parquet")

from finpulse.export.synthetic import build_synthetic, filings  # noqa: E402
from finpulse.sentiment.data import LABELS  # noqa: E402


def _lines(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_offsets_slice_back_to_the_text_and_labels_are_valid(tmp_path):
    counts = build_synthetic(tmp_path)
    docs = {d["doc_id"]: d for d in pq.read_table(tmp_path / "documents.parquet").to_pylist()}
    assert counts["documents"] == 15 and all(d["synthetic"] for d in docs.values())
    assert (counts["split_train"], counts["split_dev"], counts["split_test"]) == (11, 2, 2)
    for m in pq.read_table(tmp_path / "mentions.parquet").to_pylist():
        assert docs[m["doc_id"]]["text"][m["char_start"] : m["char_end"]] == m["surface"]
    for g in _lines(tmp_path / "sentiment_gold.jsonl"):
        assert (
            g["label"] in LABELS
            and docs[g["doc_id"]]["text"][g["char_start"] : g["char_end"]] == g["surface"]
        )
    for s in pq.read_table(tmp_path / "sentences.parquet").to_pylist():
        assert docs[s["doc_id"]]["text"][s["char_start"] : s["char_end"]] == s["text"]


def test_every_event_and_claim_points_at_a_real_sentence_and_verdicts_match_their_evidence(tmp_path):
    build_synthetic(tmp_path)
    docs = {d["doc_id"]: d["text"] for d in pq.read_table(tmp_path / "documents.parquet").to_pylist()}
    for e in _lines(tmp_path / "events_gold.jsonl"):
        assert docs[e["doc_id"]][e["trigger"][0] : e["trigger"][1]]
    kinds = set()
    for g in _lines(tmp_path / "summaries_gold.jsonl"):
        for c in g["claims"]:
            kinds.add(c["verdict"])
            assert (c["verdict"] == "unverified") == (c["evidence_sentence_idx"] == [])
    assert kinds == {"entailed", "contradicted", "unverified"}


def test_the_package_is_reproducible_and_says_it_is_synthetic(tmp_path):
    build_synthetic(tmp_path / "a")
    build_synthetic(tmp_path / "b")
    one = json.loads((tmp_path / "a" / "MANIFEST.json").read_text())
    two = json.loads((tmp_path / "b" / "MANIFEST.json").read_text())
    assert one == two and one["synthetic"] is True
    assert "synthetic" in (tmp_path / "a" / "README.md").read_text().lower()
    first = filings()[0].key
    tex = (tmp_path / "a" / "documents" / f"{first}.tex").read_text()
    assert "\\begin{document}" in tex and "Synthetic" in tex and tex.count("{") == tex.count("}")
    digest = hashlib.sha256((tmp_path / "a" / "documents" / f"{first}.txt").read_bytes()).hexdigest()
    assert digest in one["files"].values()
