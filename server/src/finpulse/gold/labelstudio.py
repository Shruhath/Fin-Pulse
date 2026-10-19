"""Label Studio: the labelling configuration, task export and annotation import.

One task is one frozen passage. Annotators mark entity spans (with the gazetteer slug when they
know it and a sentiment toward each), and event triggers with their type and arguments. Imported
annotations are stored as `gold` rows, one per annotator, passage and task. Offsets in a Label
Studio export are relative to the passage text; they are converted to offsets into
`documents.clean_text` and checked against the frozen text, and a span that does not match is
counted and skipped, not repaired.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any
from xml.sax.saxutils import quoteattr

from sqlalchemy import select
from sqlalchemy.orm import Session

from finpulse.db.models import Annotation, Document, GoldPassage
from finpulse.events.taxonomy import EventType

SENTIMENTS = ("positive", "negative", "neutral")
ENTITY_LABEL = "Entity"


def label_config() -> str:
    """The Label Studio project configuration (XML)."""
    events = "\n".join(f'    <Label value={quoteattr(t.value)} background="#8a5a00"/>' for t in EventType)
    sentiments = "\n".join(f'    <Choice value="{s}"/>' for s in SENTIMENTS)
    return f"""<View>
  <Header value="$title"/>
  <Text name="text" value="$text" granularity="word"/>

  <Header value="1. Company mentions: select the name, label it, choose its sentiment, add its slug"/>
  <Labels name="entity" toName="text">
    <Label value="{ENTITY_LABEL}" background="#2f6fa8"/>
  </Labels>
  <Choices name="sentiment" toName="text" perRegion="true" choice="single" showInline="true">
{sentiments}
  </Choices>
  <TextArea name="slug" toName="text" perRegion="true" rows="1" placeholder="gazetteer slug (optional)"/>

  <Header value="2. Events: select the sentence that states the event and label its type"/>
  <Labels name="event" toName="text">
{events}
  </Labels>
  <TextArea name="event_args" toName="text" perRegion="true" rows="2"
            placeholder="arguments as key=value; key=value (amount_inr=..., provisions=...)"/>
</View>
"""


def tasks(session: Session) -> list[dict[str, Any]]:
    """Label Studio tasks for every frozen passage, in a stable order."""
    rows = session.execute(
        select(GoldPassage, Document.title, Document.source_kind)
        .join(Document, Document.id == GoldPassage.doc_id)
        .order_by(GoldPassage.id)
    ).all()
    return [
        {
            "data": {
                "text": p.text,
                "title": title,
                "passage_id": p.id,
                "doc_id": p.doc_id,
                "source": source,
                "role": p.role,
                "sha256": p.text_sha256,
            }
        }
        for p, title, source in rows
    ]


@dataclass(slots=True)
class ImportStats:
    annotations: int = 0
    rows: int = 0
    skipped_spans: int = 0
    unknown_passages: int = 0
    by_annotator: dict[str, int] = field(default_factory=dict)


def _args(text: str) -> dict[str, str]:
    out = {}
    for part in text.split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            if k.strip() and v.strip():
                out[k.strip()] = v.strip()
    return out


def _regions(result: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Group a Label Studio result list by region id: the labelled span and its per-region answers."""
    regions: dict[str, dict[str, Any]] = defaultdict(dict)
    for r in result:
        rid, value, name = r.get("id"), r.get("value", {}), r.get("from_name")
        if rid is None:
            continue
        if r.get("type") == "labels":
            regions[rid].update(kind=name, start=value["start"], end=value["end"], text=value.get("text", ""),
                                label=(value.get("labels") or [""])[0])  # fmt: skip
        elif r.get("type") == "choices":
            regions[rid][name] = (value.get("choices") or [""])[0]
        elif r.get("type") == "textarea":
            regions[rid][name] = (value.get("text") or [""])[0]
    return regions


def import_export(session: Session, export: list[dict[str, Any]], annotators: dict[int, str]) -> ImportStats:
    """Store a Label Studio JSON export as gold annotations. Re-importing the same export adds nothing."""
    stats = ImportStats()
    passages = {p.id: p for p in session.scalars(select(GoldPassage))}
    existing = {
        (a.doc_id, a.task, a.annotator, a.payload.get("passage_id"))
        for a in session.scalars(select(Annotation).where(Annotation.label_source == "gold"))
    }
    for task in export:
        passage = passages.get(int(task.get("data", {}).get("passage_id", -1)))
        if passage is None:
            stats.unknown_passages += 1
            continue
        for ann in task.get("annotations", []):
            if ann.get("was_cancelled"):
                continue
            by = ann.get("completed_by")
            name = annotators.get(by if isinstance(by, int) else (by or {}).get("id"), f"annotator-{by}")
            spans, sentiments, events = [], [], []
            for region in _regions(ann.get("result", [])).values():
                if "start" not in region:
                    continue
                s, e = region["start"], region["end"]
                if passage.text[s:e] != region.get("text", passage.text[s:e]) or e <= s:
                    stats.skipped_spans += 1
                    continue
                abs_start, abs_end = passage.char_start + s, passage.char_start + e
                if region["kind"] == "entity":
                    spans.append({"start": abs_start, "end": abs_end, "surface": passage.text[s:e],
                                  "entity": region.get("slug") or None})  # fmt: skip
                    if region.get("sentiment") in SENTIMENTS:
                        sentiments.append({"start": abs_start, "end": abs_end, "surface": passage.text[s:e],
                                           "label": region["sentiment"]})  # fmt: skip
                elif region["kind"] == "event" and region.get("label") in {t.value for t in EventType}:
                    events.append({"type": region["label"], "trigger": {"start": abs_start, "end": abs_end},
                                   "arguments": _args(region.get("event_args", ""))})  # fmt: skip
            stats.annotations += 1
            stats.by_annotator[name] = stats.by_annotator.get(name, 0) + 1
            for task_name, key, items in (
                ("ner", "spans", spans),
                ("sentiment", "items", sentiments),
                ("event", "events", events),
            ):
                ident = (passage.doc_id, task_name, name, passage.id)
                if ident in existing:
                    continue
                existing.add(ident)
                session.add(
                    Annotation(
                        task=task_name,
                        doc_id=passage.doc_id,
                        payload={"passage_id": passage.id, key: items},
                        label_source="gold",
                        annotator=name,
                    )
                )
                stats.rows += 1
    session.flush()
    return stats


def dump(path_tasks: Any, session: Session) -> int:
    data = tasks(session)
    path_tasks.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    return len(data)
