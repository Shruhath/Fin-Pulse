"""Evaluation against the human gold passages.

Consensus: where an annotator named `adjudicated` labelled a passage that is the gold label;
otherwise the passage has a single annotator and that is the gold label; a calibration passage
with several annotators and no adjudication is left out of scoring and counted. Gold and silver
labels are never mixed: only `label_source = 'gold'` rows are read here.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from finpulse.db.models import Annotation, Document, Entity, Event, GoldPassage, Mention
from finpulse.preprocess.normalize import find_amounts
from finpulse.sentiment.data import Example

CONSENSUS = "adjudicated"


@dataclass(slots=True)
class Gold:
    """Gold payloads by passage id for one task, and how many passages could not be scored."""

    by_passage: dict[int, dict[str, Any]] = field(default_factory=dict)
    unadjudicated: int = 0


def load_gold(session: Session, task: str) -> Gold:
    per: dict[int, dict[str, dict[str, Any]]] = defaultdict(dict)
    for a in session.scalars(
        select(Annotation).where(Annotation.task == task, Annotation.label_source == "gold")
    ):
        per[a.payload["passage_id"]][a.annotator] = a.payload
    gold = Gold()
    for pid, by_annotator in per.items():
        if CONSENSUS in by_annotator:
            gold.by_passage[pid] = by_annotator[CONSENSUS]
        elif len(by_annotator) == 1:
            gold.by_passage[pid] = next(iter(by_annotator.values()))
        else:
            gold.unadjudicated += 1
    return gold


def _prf(tp: int, system: int, gold: int) -> tuple[float, float, float]:
    p = tp / system if system else 0.0
    r = tp / gold if gold else 0.0
    return p, r, (2 * p * r / (p + r) if p + r else 0.0)


# --------------------------------------------------------------------------- events


def _norm_value(key: str, value: str) -> object:
    if key.endswith("_inr") or key == "amount":
        found = find_amounts(value if re.search(r"rs|inr|₹", value, re.I) else f"Rs. {value}")
        if found:
            return found[0].inr
        try:
            return Decimal(value.replace(",", ""))
        except ArithmeticError:
            pass
    if key == "provisions":
        return frozenset(
            re.sub(r"\s+", " ", p).strip().lower() for p in re.split(r"[;|]", value) if p.strip()
        )
    return re.sub(r"\s+", " ", value).strip().lower()


def _arg_pairs(args: dict[str, str], amount: Decimal | None) -> set[tuple[str, object]]:
    pairs = {(k.lower(), _norm_value(k.lower(), str(v))) for k, v in args.items() if v not in (None, "")}
    if amount is not None:
        pairs.add(("amount_inr", amount))
    return {p for p in pairs if p[0] not in {"amounts_stated", "amount"}}


def evaluate_events(session: Session, extractor: str) -> dict[str, float]:
    """Type and argument F1 of one extractor (`rules` or `llm`) against the gold event annotations."""
    gold = load_gold(session, "event")
    passages = {
        p.id: p for p in session.scalars(select(GoldPassage).where(GoldPassage.id.in_(gold.by_passage)))
    }
    tp = n_sys = n_gold = arg_tp = arg_sys = arg_gold = valid = 0
    per_type: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])  # tp, system, gold
    for pid, payload in gold.by_passage.items():
        passage = passages[pid]
        system = [
            e
            for e in session.scalars(
                select(Event).where(Event.doc_id == passage.doc_id, Event.extractor == extractor)
            )
            if e.trigger_start is not None and passage.char_start <= e.trigger_start < passage.char_end
        ]
        gold_events = payload.get("events", [])
        n_sys += len(system)
        n_gold += len(gold_events)
        valid += sum(e.schema_valid for e in system)
        used: set[int] = set()
        for g in gold_events:
            per_type[g["type"]][2] += 1
            gs, ge = g["trigger"]["start"], g["trigger"]["end"]
            match = next(
                (
                    e
                    for e in system
                    if e.id not in used
                    and e.type == g["type"]
                    and e.trigger_start < ge
                    and gs < e.trigger_end
                ),
                None,
            )
            if match is None:
                continue
            used.add(match.id)
            tp += 1
            per_type[g["type"]][0] += 1
            gp = _arg_pairs(g.get("arguments", {}), None)
            sp = _arg_pairs(match.arguments or {}, match.amount_inr)
            arg_tp += len(gp & sp)
            arg_gold += len(gp)
            arg_sys += len(sp)
        for e in system:
            per_type[e.type][1] += 1
    p, r, f1 = _prf(tp, n_sys, n_gold)
    _, _, arg_f1 = _prf(arg_tp, arg_sys, arg_gold)
    macro = [_prf(*counts)[2] for counts in per_type.values() if counts[2]]
    return {
        "typePrecision": p,
        "typeRecall": r,
        "typeF1": f1,
        "typeMacroF1": sum(macro) / len(macro) if macro else 0.0,
        "argF1": arg_f1,
        "validity": valid / n_sys if n_sys else 1.0,
        "n": float(len(gold.by_passage)),
        "goldEvents": float(n_gold),
        "systemEvents": float(n_sys),
        "unadjudicated": float(gold.unadjudicated),
    }


# --------------------------------------------------------------------------- entities


def evaluate_ner(session: Session) -> dict[str, float]:
    """Exact-span F1 of the entity matcher on gold spans, and linking accuracy where gold names the entity."""
    gold = load_gold(session, "ner")
    passages = {
        p.id: p for p in session.scalars(select(GoldPassage).where(GoldPassage.id.in_(gold.by_passage)))
    }
    slugs = {e.id: e.slug for e in session.scalars(select(Entity))}
    tp = n_sys = n_gold = link_ok = link_total = 0
    for pid, payload in gold.by_passage.items():
        passage = passages[pid]
        mentions = {
            (m.char_start, m.char_end): slugs.get(m.entity_id)
            for m in session.scalars(select(Mention).where(Mention.doc_id == passage.doc_id))
            if passage.char_start <= m.char_start and m.char_end <= passage.char_end
        }
        spans = payload.get("spans", [])
        n_sys += len(mentions)
        n_gold += len(spans)
        for s in spans:
            key = (s["start"], s["end"])
            tp += key in mentions
            if s.get("entity"):
                link_total += 1
                link_ok += key in mentions and mentions[key] == s["entity"]
    p, r, f1 = _prf(tp, n_sys, n_gold)
    return {
        "spanPrecision": p,
        "spanRecall": r,
        "spanF1": f1,
        "linkAcc": link_ok / link_total if link_total else 0.0,
        "n": float(len(gold.by_passage)),
        "goldSpans": float(n_gold),
        "unadjudicated": float(gold.unadjudicated),
    }


# --------------------------------------------------------------------------- sentiment


def sentiment_examples(session: Session) -> list[Example]:
    """Gold entity sentiment as examples whose offsets are relative to the passage text."""
    gold = load_gold(session, "sentiment")
    passages = {
        p.id: p for p in session.scalars(select(GoldPassage).where(GoldPassage.id.in_(gold.by_passage)))
    }
    out: list[Example] = []
    for pid, payload in gold.by_passage.items():
        passage = passages[pid]
        for item in payload.get("items", []):
            out.append(
                Example(
                    passage.text,
                    item["start"] - passage.char_start,
                    item["end"] - passage.char_start,
                    item["label"],
                    "FinPulse gold",
                    "test",
                )
            )
    return out


def document_titles(session: Session, doc_ids: list[int]) -> dict[int, str]:
    return {
        i: t for i, t in session.execute(select(Document.id, Document.title).where(Document.id.in_(doc_ids)))
    }
