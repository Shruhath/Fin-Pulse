"""Build the IEEE DataPort package: `finpulse-corpus-v1/`.

By default the package holds annotations, offsets, hashes and URLs only, never the text of the
regulatory documents, because SEBI asks for permission before its orders are republished and the
orders name individuals. Pass `include_text=True` once that permission is in hand (PANs are then
masked in the text). Gold (human) and silver (machine) labels go to separate files and are never
merged. The SEntFiN aliases in the gazetteer are left out: that dataset asks to be cited, not
re-hosted. Individuals (entities of kind `person`) are not exported, and the words kept from the
orders (titles, event arguments, claim text) are passed through `privacy.Redactor` first.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
from sqlalchemy import select
from sqlalchemy.orm import Session

from finpulse.core.settings import REPO_DIR
from finpulse.db.models import (
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
from finpulse.export.privacy import Redactor, looks_like_individual
from finpulse.preprocess.normalize import mask_pan
from finpulse.sentiment.data import split_of

LICENSE = """FinPulse corpus annotations: Creative Commons Attribution 4.0 International (CC BY 4.0)
https://creativecommons.org/licenses/by/4.0/legalcode

You may share and adapt this material, including commercially, if you give appropriate credit,
link to the licence and say whether changes were made. The licence covers the annotations, offsets,
labels and derived metadata in this package. It does not cover the source documents, which remain
the property of their publishers (SEBI, IBBI and others) and are not included unless the manifest
says `include_text: true`.
"""

NOTE = Path(__file__).with_name("package_readme.md").read_text(encoding="utf-8")


_DEIDENTIFIED = NOTE[NOTE.index("## What was removed") : NOTE.index("## Load it")]
_WORDS_FREE = """## What was removed

The document text is not included, and neither is any other field made of words taken from an order:
the document title, the arguments of an event and the text of a claim are empty (null). What remains is
offsets, hashes, labels, verdicts, scores, counts and the names of listed companies and banks. A claim
still carries its verdict, its NLI scores and the sentence it was checked against, as ids.

"""


@dataclass(slots=True)
class Manifest:
    include_text: bool
    counts: dict[str, int] = field(default_factory=dict)
    files: dict[str, str] = field(default_factory=dict)


def _git_sha() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO_DIR, capture_output=True, text=True, check=True
        )
        return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def _file_hash(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _parquet(path: Path, rows: list[dict[str, Any]], columns: dict[str, pa.DataType]) -> int:
    table = pa.Table.from_pylist(rows, schema=pa.schema(list(columns.items())))
    pq.write_table(table, path, compression="zstd")
    return len(rows)


def _jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    n = 0
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
            n += 1
    return n


def export_dataport(
    session: Session,
    out_dir: Path,
    *,
    include_text: bool = False,
    extra_names: Iterable[str] = (),
    words: bool = True,
) -> Manifest:
    """`words=False` also leaves out every field that carries words taken from an order: the document
    title, the arguments of an event and the text of a claim. What remains is offsets, hashes, labels,
    verdicts, scores and counts, so nothing in the package can name anyone."""
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "splits").mkdir(exist_ok=True)
    manifest = Manifest(include_text=include_text)
    exported_entities = {
        e.id: e
        for e in session.scalars(
            select(Entity).where(Entity.kind.in_(("company", "bank"))).order_by(Entity.id)
        )
        if not looks_like_individual(e.canonical_name, listed=bool(e.nse_symbol or e.isin))
    }
    person_ids = list(session.scalars(select(Entity.id).where(Entity.kind == "person")))
    redact = Redactor(
        [
            *session.scalars(select(Entity.canonical_name).where(Entity.id.in_(person_ids))),
            *session.scalars(select(EntityAlias.alias).where(EntityAlias.entity_id.in_(person_ids))),
        ],
        extra_names,
    )
    docs = list(
        session.scalars(
            select(Document)
            .where(Document.status.in_(("parsed", "analysed")), Document.is_submission.is_(False))
            .order_by(Document.id)
        )
    )
    doc_ids = {d.id for d in docs}

    # documents
    doc_rows = [
        {
            "doc_id": d.id,
            "source_kind": d.source_kind,
            "doc_type": d.doc_type,
            "title": redact.title(d.title) if words else None,
            "url": d.url,
            "published_at": d.published_at,
            "sha256": d.raw_sha256,
            "n_words": d.n_words,
            "n_pages": d.n_pages,
            "ocr_used": d.ocr_used,
            "near_duplicate_of": d.minhash_cluster if d.minhash_cluster != d.id else None,
            "text": mask_pan(d.clean_text) if include_text else None,
        }
        for d in docs
    ]
    manifest.counts["titles_redacted"] = sum(
        row["title"] != d.title for row, d in zip(doc_rows, docs, strict=True)
    )
    manifest.counts["documents"] = _parquet(
        out_dir / "documents.parquet",
        doc_rows,
        {
            "doc_id": pa.int64(),
            "source_kind": pa.string(),
            "doc_type": pa.string(),
            "title": pa.string(),
            "url": pa.string(),
            "published_at": pa.date32(),
            "sha256": pa.string(),
            "n_words": pa.int32(),
            "n_pages": pa.int32(),
            "ocr_used": pa.bool_(),
            "near_duplicate_of": pa.int64(),
            "text": pa.string(),
        },
    )

    # sentences
    sent_rows = [
        {
            "doc_id": s.doc_id,
            "idx": s.idx,
            "char_start": s.char_start,
            "char_end": s.char_end,
            "kept_after_prune": s.kept_after_prune,
            "sha256": hashlib.sha256(s.text.encode()).hexdigest(),
            "text": mask_pan(s.text) if include_text else None,
        }
        for s in session.scalars(select(Sentence).order_by(Sentence.doc_id, Sentence.idx))
        if s.doc_id in doc_ids
    ]
    manifest.counts["sentences"] = _parquet(
        out_dir / "sentences.parquet",
        sent_rows,
        {
            "doc_id": pa.int64(),
            "idx": pa.int32(),
            "char_start": pa.int32(),
            "char_end": pa.int32(),
            "kept_after_prune": pa.bool_(),
            "sha256": pa.string(),
            "text": pa.string(),
        },
    )

    # entities and gazetteer (no SEntFiN aliases, no individuals)
    manifest.counts["entities"] = _parquet(
        out_dir / "entities.parquet",
        [
            {
                "slug": e.slug,
                "canonical_name": e.canonical_name,
                "nse_symbol": e.nse_symbol,
                "isin": e.isin,
                "sector": e.sector,
                "kind": e.kind,
            }
            for e in exported_entities.values()
        ],
        {
            "slug": pa.string(),
            "canonical_name": pa.string(),
            "nse_symbol": pa.string(),
            "isin": pa.string(),
            "sector": pa.string(),
            "kind": pa.string(),
        },
    )
    gaz = ["alias,slug,origin"]
    for alias, ent_id, origin in session.execute(
        select(EntityAlias.alias, EntityAlias.entity_id, EntityAlias.origin).order_by(EntityAlias.id)
    ):
        if ent_id in exported_entities and origin != "sentfin":
            gaz.append(f'"{alias.replace(chr(34), chr(34) * 2)}",{exported_entities[ent_id].slug},{origin}')
    (out_dir / "entity_gazetteer.csv").write_text("\n".join(gaz) + "\n", encoding="utf-8")
    manifest.counts["gazetteer_aliases"] = len(gaz) - 1

    # mentions (silver: produced by the matcher)
    mention_rows = [
        {
            "doc_id": m.doc_id,
            "char_start": m.char_start,
            "char_end": m.char_end,
            "entity": exported_entities[m.entity_id].slug,
            "ner_model": m.ner_model,
            "link_method": m.link_method,
            "link_score": m.link_score,
            "surface": m.surface if include_text else None,
        }
        for m in session.scalars(
            select(Mention).where(Mention.entity_id.in_(exported_entities)).order_by(Mention.id)
        )
        if m.doc_id in doc_ids
    ]
    manifest.counts["mentions"] = _parquet(
        out_dir / "mentions.parquet",
        mention_rows,
        {
            "doc_id": pa.int64(),
            "char_start": pa.int32(),
            "char_end": pa.int32(),
            "entity": pa.string(),
            "ner_model": pa.string(),
            "link_method": pa.string(),
            "link_score": pa.float32(),
            "surface": pa.string(),
        },
    )

    # sentiment: gold (human) and silver (models) in separate files
    gold_sentiment = (
        {"passage_id": a.payload["passage_id"], "doc_id": a.doc_id, "annotator": a.annotator, **item}
        for a in session.scalars(
            select(Annotation).where(Annotation.task == "sentiment", Annotation.label_source == "gold")
        )
        for item in a.payload.get("items", [])
    )
    manifest.counts["sentiment_gold"] = _jsonl(
        out_dir / "sentiment_gold.jsonl", _strip_surface(gold_sentiment, include_text)
    )
    silver = (
        {
            "doc_id": m.doc_id,
            "char_start": m.char_start,
            "char_end": m.char_end,
            "entity": exported_entities[m.entity_id].slug,
            "model": ms.model_version,
            "label": ms.label,
            "p_pos": ms.p_pos,
            "p_neg": ms.p_neg,
            "p_neu": ms.p_neu,
            "confidence": ms.confidence,
        }
        for ms, m in session.execute(
            select(MentionSentiment, Mention).join(Mention, Mention.id == MentionSentiment.mention_id)
        )
        if m.entity_id in exported_entities and m.doc_id in doc_ids
    )
    manifest.counts["sentiment_silver"] = _jsonl(out_dir / "sentiment_silver.jsonl", silver)

    # events
    gold_events = (
        {
            "passage_id": a.payload["passage_id"],
            "doc_id": a.doc_id,
            "annotator": a.annotator,
            **{**ev, "arguments": redact.value(ev.get("arguments"))},
        }
        for a in session.scalars(
            select(Annotation).where(Annotation.task == "event", Annotation.label_source == "gold")
        )
        for ev in a.payload.get("events", [])
    )
    manifest.counts["events_gold"] = _jsonl(out_dir / "events_gold.jsonl", gold_events)
    slug_of = {i: e.slug for i, e in exported_entities.items()}
    silver_events = []
    manifest.counts["event_arguments_redacted"] = 0
    for e in session.scalars(select(Event).order_by(Event.id)):
        if e.doc_id not in doc_ids:
            continue
        arguments = redact.value(e.arguments)
        manifest.counts["event_arguments_redacted"] += arguments != e.arguments
        silver_events.append(
            {
                "doc_id": e.doc_id,
                "entity": slug_of.get(e.entity_id),
                "type": e.type,
                "trigger": [e.trigger_start, e.trigger_end],
                "arguments": arguments if words else None,
                "amount_inr": e.amount_inr,
                "event_date": e.event_date,
                "extractor": e.extractor,
                "schema_valid": e.schema_valid,
            }
        )
    manifest.counts["events_silver"] = _jsonl(out_dir / "events_silver.jsonl", silver_events)

    # summaries
    gold_summaries = (
        {
            "passage_id": a.payload["passage_id"],
            "doc_id": a.doc_id,
            "annotator": a.annotator,
            "claims": redact.value(a.payload["claims"]),
        }
        for a in session.scalars(
            select(Annotation).where(Annotation.task == "summary", Annotation.label_source == "gold")
        )
    )
    manifest.counts["summaries_gold"] = _jsonl(out_dir / "summaries_gold.jsonl", gold_summaries)
    silver_summaries = []
    manifest.counts["claims_redacted"] = 0
    for summary in session.scalars(select(Summary).order_by(Summary.id)):
        claims = list(
            session.scalars(select(Claim).where(Claim.summary_id == summary.id).order_by(Claim.idx))
        )
        manifest.counts["claims_redacted"] += sum(redact.text(c.text) != c.text for c in claims)
        silver_summaries.append(
            {
                "summary_id": summary.id,
                "scope": summary.scope,
                "doc_id": summary.doc_id,
                "entity": slug_of.get(summary.entity_id),
                "model": summary.model,
                "prompt_version": summary.prompt_version,
                "claims": [
                    {
                        "text": redact.text(c.text) if words else None,
                        "verification": c.verification,
                        "nli_entail": c.nli_entail,
                        "nli_contra": c.nli_contra,
                        "evidence_sentence_id": c.evidence_sentence_id,
                        "cited": c.cited,
                    }
                    for c in claims
                ],
            }
        )
    manifest.counts["summaries_silver"] = _jsonl(out_dir / "summaries_silver.jsonl", silver_summaries)

    # metrics and splits
    manifest.counts["eval_results"] = _jsonl(
        out_dir / "eval_results.jsonl",
        (
            {
                "stage": r.stage,
                "model": r.model,
                "baseline": r.baseline,
                "dataset": r.dataset,
                "split": r.split,
                "indian": r.indian,
                "metrics": r.metrics,
                "git_sha": r.git_sha,
                "data_hash": r.data_hash,
            }
            for r in session.scalars(select(EvalResult).order_by(EvalResult.id))
        ),
    )
    splits: dict[str, list[int]] = {"train": [], "dev": [], "test": []}
    for d in docs:
        splits[split_of(d.raw_sha256)].append(d.id)
    for name, ids in splits.items():
        (out_dir / "splits" / f"{name}.txt").write_text("".join(f"{i}\n" for i in ids))
        manifest.counts[f"split_{name}"] = len(ids)

    readme = NOTE if words else NOTE.replace(_DEIDENTIFIED, _WORDS_FREE)
    (out_dir / "README.md").write_text(readme, encoding="utf-8")
    (out_dir / "LICENSE.txt").write_text(LICENSE, encoding="utf-8")
    files = sorted(p for p in out_dir.rglob("*") if p.is_file() and p.name != "MANIFEST.json")
    manifest.files = {str(p.relative_to(out_dir)): _file_hash(p) for p in files}
    (out_dir / "MANIFEST.json").write_text(
        json.dumps(
            {
                "name": "finpulse-corpus-v1",
                "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "git_sha": _git_sha(),
                "include_text": include_text,
                "words": words,
                "counts": manifest.counts,
                "files": manifest.files,
            },
            indent=2,
        )
        + "\n"
    )
    return manifest


def _strip_surface(rows: Iterable[dict[str, Any]], include_text: bool) -> Iterable[dict[str, Any]]:
    for row in rows:
        if not include_text:
            row = {k: v for k, v in row.items() if k != "surface"}
        yield row
