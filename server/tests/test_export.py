import hashlib
import json
from datetime import date

import pytest

pq = pytest.importorskip("pyarrow.parquet")  # CI installs the export extra and checks that pyarrow imports

from finpulse.db.models import (  # noqa: E402
    Annotation,
    Claim,
    Document,
    Entity,
    EntityAlias,
    EvalResult,
    Event,
    Mention,
    MentionSentiment,
    Sentence,
    Summary,
)
from finpulse.export.dataport import export_dataport  # noqa: E402

pytestmark = pytest.mark.db

TEXT = "SEBI imposed a penalty on Yes Bank. The noticee PAN ABCDE1234F paid it promptly in full."


def _seed(db):
    doc = Document(
        source_kind="SEBI", title="Order", raw_sha256="a" * 64, clean_text=TEXT, n_words=15,
        status="analysed", doc_type="SEBI adjudication order", published_at=date(2026, 5, 1),
        url="https://example.test/o",
    )  # fmt: skip
    db.add(doc)
    yes = Entity(slug="yes-bank", canonical_name="Yes Bank Limited", nse_symbol="YESBANK", kind="bank")
    person = Entity(slug="some-person", canonical_name="Some Person", kind="person")
    db.add_all([yes, person])
    db.flush()
    doc.minhash_cluster = doc.id
    db.add_all(
        [
            EntityAlias(entity_id=yes.id, alias="Yes Bank Limited", alias_norm="yes bank", origin="nse"),
            EntityAlias(
                entity_id=yes.id, alias="Yes Bank, YESBANK", alias_norm="yes bank yesbank", origin="sentfin"
            ),
            EntityAlias(entity_id=person.id, alias="Some Person", alias_norm="some person", origin="corpus"),
        ]
    )
    first = Sentence(doc_id=doc.id, idx=0, char_start=0, char_end=36, text=TEXT[:36])
    second = Sentence(doc_id=doc.id, idx=1, char_start=37, char_end=len(TEXT), text=TEXT[37:])
    db.add_all([first, second])
    db.flush()
    m1 = Mention(
        doc_id=doc.id,
        sentence_id=first.id,
        entity_id=yes.id,
        char_start=28,
        char_end=36,
        surface="Yes Bank",
        ner_model="gz",
    )
    m2 = Mention(
        doc_id=doc.id,
        sentence_id=second.id,
        entity_id=person.id,
        char_start=37,
        char_end=40,
        surface="The",
        ner_model="gz",
    )
    db.add_all([m1, m2])
    db.flush()
    db.add(
        MentionSentiment(
            mention_id=m1.id,
            model_version="tfidf-lr@x",
            label="negative",
            p_pos=0.1,
            p_neg=0.8,
            p_neu=0.1,
            confidence=0.8,
        )
    )
    db.add(
        Event(
            doc_id=doc.id,
            entity_id=yes.id,
            type="SEBI Penalty",
            trigger_start=0,
            trigger_end=36,
            arguments={"action": "penalty"},
            extractor="rules",
        )
    )
    db.add(
        Annotation(
            task="sentiment",
            doc_id=doc.id,
            label_source="gold",
            annotator="asha",
            payload={
                "passage_id": 1,
                "items": [{"start": 28, "end": 36, "surface": "Yes Bank", "label": "negative"}],
            },
        )
    )
    db.add(
        Annotation(
            task="event",
            doc_id=doc.id,
            label_source="gold",
            annotator="asha",
            payload={
                "passage_id": 1,
                "events": [{"type": "SEBI Penalty", "trigger": {"start": 0, "end": 36}, "arguments": {}}],
            },
        )
    )
    summary = Summary(scope="document", doc_id=doc.id, model="llama", prompt_version="summary-v1")
    db.add(summary)
    db.flush()
    db.add(
        Claim(
            summary_id=summary.id,
            idx=0,
            text="SEBI fined Yes Bank.",
            verification="entailed",
            nli_entail=0.9,
            nli_contra=0.01,
            cited=[first.id],
        )
    )
    db.add(
        EvalResult(
            stage="sentiment",
            model="m",
            baseline=True,
            dataset="d",
            split="test",
            indian=True,
            metrics={"macroF1": 0.8},
        )
    )
    db.flush()
    return doc


def _lines(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_the_default_package_holds_no_document_text(db, tmp_path):
    doc = _seed(db)
    manifest = export_dataport(db, tmp_path / "pkg")
    out = tmp_path / "pkg"
    assert manifest.include_text is False
    documents = pq.read_table(out / "documents.parquet").to_pylist()
    assert (
        [d["text"] for d in documents] == [None]
        and documents[0]["sha256"] == "a" * 64
        and documents[0]["title"] == "Order"
    )
    sentences = pq.read_table(out / "sentences.parquet").to_pylist()
    assert all(s["text"] is None for s in sentences)
    assert sentences[0]["sha256"] == hashlib.sha256(TEXT[:36].encode()).hexdigest()
    mentions = pq.read_table(out / "mentions.parquet").to_pylist()
    assert [(m["entity"], m["surface"]) for m in mentions] == [
        ("yes-bank", None)
    ]  # the person is not exported
    assert not any(
        doc.title in p.read_text(errors="ignore") for p in [out / "README.md", out / "LICENSE.txt"]
    )


def test_gold_and_silver_are_separate_files_and_individuals_and_sentfin_aliases_are_left_out(db, tmp_path):
    _seed(db)
    export_dataport(db, tmp_path / "pkg")
    out = tmp_path / "pkg"
    assert [r["label"] for r in _lines(out / "sentiment_gold.jsonl")] == ["negative"]
    assert "surface" not in _lines(out / "sentiment_gold.jsonl")[0]
    (silver,) = _lines(out / "sentiment_silver.jsonl")
    assert silver["model"] == "tfidf-lr@x" and silver["entity"] == "yes-bank"
    assert [e["type"] for e in _lines(out / "events_gold.jsonl")] == ["SEBI Penalty"]
    assert [e["extractor"] for e in _lines(out / "events_silver.jsonl")] == ["rules"]
    assert not (
        set(_lines(out / "sentiment_gold.jsonl")[0]) & {"p_pos", "model"}
    )  # gold never carries model output
    gazetteer = (out / "entity_gazetteer.csv").read_text()
    assert "sentfin" not in gazetteer and "Some Person" not in gazetteer and "yes-bank,nse" in gazetteer
    entities = pq.read_table(out / "entities.parquet").to_pylist()
    assert [e["slug"] for e in entities] == ["yes-bank"]
    (claim_summary,) = _lines(out / "summaries_silver.jsonl")
    assert (
        claim_summary["claims"][0]["verification"] == "entailed"
        and _lines(out / "summaries_gold.jsonl") == []
    )


def test_manifest_hashes_every_file_and_splits_cover_every_document_once(db, tmp_path):
    _seed(db)
    manifest = export_dataport(db, tmp_path / "pkg")
    out = tmp_path / "pkg"
    recorded = json.loads((out / "MANIFEST.json").read_text())
    assert recorded["include_text"] is False and recorded["counts"]["documents"] == 1
    for name, digest in recorded["files"].items():
        assert hashlib.sha256((out / name).read_bytes()).hexdigest() == digest
    assert {"README.md", "LICENSE.txt", "documents.parquet", "splits/train.txt"} <= set(manifest.files)
    ids = [
        line
        for split in ("train", "dev", "test")
        for line in (out / "splits" / f"{split}.txt").read_text().split()
    ]
    assert len(ids) == 1
    assert "Creative Commons Attribution 4.0" in (out / "LICENSE.txt").read_text()


def test_including_text_masks_pan_numbers_and_says_so_in_the_manifest(db, tmp_path):
    _seed(db)
    export_dataport(db, tmp_path / "pkg", include_text=True)
    out = tmp_path / "pkg"
    (doc,) = pq.read_table(out / "documents.parquet").to_pylist()
    assert "ABCDE1234F" not in doc["text"] and "XXXXXXXXXX" in doc["text"] and len(doc["text"]) == len(TEXT)
    assert json.loads((out / "MANIFEST.json").read_text())["include_text"] is True
    mentions = pq.read_table(out / "mentions.parquet").to_pylist()
    assert mentions[0]["surface"] == "Yes Bank"


def test_titles_event_arguments_and_claims_are_cleaned_of_personal_data(db, tmp_path):
    doc = _seed(db)
    doc.title = "Consent order against Some Person in the matter of Yes Bank Limited"
    summary = db.query(Summary).one()
    db.add(
        Claim(
            summary_id=summary.id,
            idx=1,
            text="Some Person can be reached at sp@example.test.",
            verification="unverified",
            cited=[],
        )
    )
    event = db.query(Event).one()
    event.arguments = {"noticee": "Some Person", "action": "penalty"}
    db.flush()
    export_dataport(db, tmp_path / "pkg")
    out = tmp_path / "pkg"
    (row,) = pq.read_table(out / "documents.parquet").to_pylist()
    assert row["title"] == "Consent order against [individual] in the matter of Yes Bank Limited"
    (silver,) = _lines(out / "events_silver.jsonl")
    assert silver["arguments"] == {"noticee": "[individual]", "action": "penalty"}
    (summary_row,) = _lines(out / "summaries_silver.jsonl")
    assert [c["text"] for c in summary_row["claims"]] == [
        "SEBI fined Yes Bank.",
        "[individual] can be reached at [email].",
    ]
    counts = json.loads((out / "MANIFEST.json").read_text())["counts"]
    assert (counts["titles_redacted"], counts["event_arguments_redacted"], counts["claims_redacted"]) == (
        1,
        1,
        1,
    )
    everything = "".join(
        p.read_text(errors="ignore") for p in out.rglob("*") if p.suffix in {".jsonl", ".json", ".md"}
    )
    assert "Some Person" not in everything and "sp@example.test" not in everything


def test_a_document_analysed_through_the_analyze_page_is_not_exported(db, tmp_path):
    _seed(db)
    db.add(
        Document(source_kind="NEWS", title="pasted", raw_sha256="b" * 64, clean_text="x", n_words=1,
                 status="analysed", is_submission=True)
    )  # fmt: skip
    db.flush()
    other = db.query(Document).filter(Document.is_submission.is_(True)).one()
    db.add(Summary(scope="document", doc_id=other.id, model="llama", prompt_version="summary-v1"))
    db.flush()
    export_dataport(db, tmp_path / "pkg")
    assert len(pq.read_table(tmp_path / "pkg" / "documents.parquet")) == 1
    assert (
        len(_lines(tmp_path / "pkg" / "summaries_silver.jsonl")) == 1
    )  # the submission's summary is left out


def test_the_words_free_package_has_no_title_event_arguments_or_claim_text(db, tmp_path):
    _seed(db)
    export_dataport(db, tmp_path / "pkg", words=False)
    out = tmp_path / "pkg"
    (row,) = pq.read_table(out / "documents.parquet").to_pylist()
    assert row["title"] is None and row["text"] is None and row["sha256"] == "a" * 64
    (event,) = _lines(out / "events_silver.jsonl")
    assert event["arguments"] is None and event["type"] == "SEBI Penalty"
    (summary,) = _lines(out / "summaries_silver.jsonl")
    (claim,) = summary["claims"]
    assert (
        claim["text"] is None
        and claim["verification"] == "entailed"
        and claim["nli_entail"] == pytest.approx(0.9)
    )
    assert json.loads((out / "MANIFEST.json").read_text())["words"] is False
    assert "empty (null)" in (out / "README.md").read_text()
