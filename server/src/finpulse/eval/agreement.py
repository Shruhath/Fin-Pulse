"""Inter-annotator agreement on the shared calibration passages.

Sentiment: Cohen's kappa (two annotators) or Fleiss' kappa (three or more) over entity spans that
every annotator marked. Event type: kappa over passage x event-type presence. Entity spans: mean
pairwise F1 over exact spans. The gates are the thresholds below which the guideline is revised
and the passages are labelled again before the rest of the gold set is started.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from itertools import combinations

from sqlalchemy import select
from sqlalchemy.orm import Session

from finpulse.db.models import Agreement, Annotation, GoldPassage
from finpulse.events.taxonomy import EventType
from finpulse.sentiment.data import LABELS

GATES = {"sentiment": 0.70, "event": 0.70, "ner": 0.80}


def cohen_kappa(a: list[str], b: list[str]) -> float:
    n = len(a)
    if n == 0:
        return float("nan")
    observed = sum(x == y for x, y in zip(a, b, strict=True)) / n
    cats = set(a) | set(b)
    expected = sum((a.count(c) / n) * (b.count(c) / n) for c in cats)
    return 1.0 if expected == 1 else (observed - expected) / (1 - expected)


def fleiss_kappa(counts: list[list[int]]) -> float:
    """`counts[i][j]` is how many raters put item i in category j; every row sums to the same n."""
    items = len(counts)
    if items == 0:
        return float("nan")
    raters = sum(counts[0])
    p_cat = [sum(row[j] for row in counts) / (items * raters) for j in range(len(counts[0]))]
    p_item = [(sum(c * c for c in row) - raters) / (raters * (raters - 1)) for row in counts]
    observed = sum(p_item) / items
    expected = sum(p * p for p in p_cat)
    return 1.0 if expected == 1 else (observed - expected) / (1 - expected)


def span_f1(a: set[tuple[int, int]], b: set[tuple[int, int]]) -> float:
    if not a and not b:
        return 1.0
    tp = len(a & b)
    if tp == 0:
        return 0.0
    p, r = tp / len(b), tp / len(a)
    return 2 * p * r / (p + r)


@dataclass(frozen=True, slots=True)
class AgreementRow:
    task: str
    measure: str
    annotators: tuple[str, ...]
    value: float
    items: int

    @property
    def passed(self) -> bool:
        return self.value >= GATES[self.task]


def _kappa(
    labels_by_annotator: dict[str, dict[object, str]], categories: tuple[str, ...]
) -> tuple[str, float, int] | None:
    names = sorted(labels_by_annotator)
    common = set.intersection(*(set(v) for v in labels_by_annotator.values())) if names else set()
    if len(names) < 2 or not common:
        return None
    if len(names) == 2:
        items = sorted(common, key=str)
        return (
            "cohen_kappa",
            cohen_kappa(
                [labels_by_annotator[names[0]][i] for i in items],
                [labels_by_annotator[names[1]][i] for i in items],
            ),
            len(items),
        )
    table = [[sum(labels_by_annotator[n][i] == c for n in names) for c in categories] for i in common]
    return "fleiss_kappa", fleiss_kappa(table), len(table)


def compute_agreement(session: Session) -> list[AgreementRow]:
    """Agreement per task on calibration passages that two or more people labelled; stored in `agreements`."""
    calib = {p.id for p in session.scalars(select(GoldPassage).where(GoldPassage.role == "calibration"))}
    sentiment: dict[str, dict[object, str]] = defaultdict(dict)
    spans: dict[str, dict[int, set[tuple[int, int]]]] = defaultdict(lambda: defaultdict(set))
    events: dict[str, dict[object, str]] = defaultdict(dict)
    for a in session.scalars(select(Annotation).where(Annotation.label_source == "gold")):
        pid = a.payload.get("passage_id")
        if pid not in calib:
            continue
        if a.task == "sentiment":
            for it in a.payload.get("items", []):
                sentiment[a.annotator][(pid, it["start"], it["end"])] = it["label"]
        elif a.task == "ner":
            spans[a.annotator][pid] |= {(s["start"], s["end"]) for s in a.payload.get("spans", [])}
        elif a.task == "event":
            present = {e["type"] for e in a.payload.get("events", [])}
            for t in EventType:
                events[a.annotator][(pid, t.value)] = "yes" if t.value in present else "no"
        # a person who labelled a passage with no events still counts: their absent cells are "no"

    rows: list[AgreementRow] = []
    for task, data, cats in (("sentiment", sentiment, LABELS), ("event", events, ("yes", "no"))):
        got = _kappa(data, cats)
        if got:
            measure, value, items = got
            rows.append(AgreementRow(task, measure, tuple(sorted(data)), value, items))
    names = sorted(spans)
    if len(names) >= 2:
        shared = set.intersection(*(set(spans[n]) for n in names))
        scores = [span_f1(spans[x][p], spans[y][p]) for p in shared for x, y in combinations(names, 2)]
        if scores:
            rows.append(AgreementRow("ner", "span_f1", tuple(names), sum(scores) / len(scores), len(shared)))

    for r in rows:
        key = ",".join(r.annotators)
        row = session.scalar(
            select(Agreement).where(
                Agreement.task == r.task, Agreement.measure == r.measure, Agreement.annotators == key
            )
        )
        if row is None:
            session.add(
                Agreement(task=r.task, measure=r.measure, annotators=key, value=r.value, items=r.items)
            )
        else:
            row.value, row.items = r.value, r.items
    session.flush()
    return rows
