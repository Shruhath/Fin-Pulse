"""Rule-based event extraction for SEBI and NCLT documents.

This is the deterministic baseline the LLM extractor is compared against. It reads the
operative sentence of an order (where the penalty is imposed, the restraint directed, the
settlement amount fixed, or the application admitted) and keeps an event only when that
sentence is found. An argument that the text does not state is left out, never guessed.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from finpulse.core.offsets import Span
from finpulse.preprocess.normalize import find_amounts, find_statutes

from .taxonomy import EventType, validate_arguments

_I = re.IGNORECASE

_HEREBY_IMPOSE = re.compile(
    r"\bhereby\s+impos\w*|\bI\s+(?:\w+\s+){0,3}impos\w*|\bwe\s+(?:\w+\s+){0,3}impos\w*", _I
)
_PENALTY = re.compile(r"\bpenalt(?:y|ies)\b", _I)
_FOLLOWING = re.compile(r"\bfollowing\s+penalt|\bpenalt\w*\s+(?:as\s+follows|under\s+the\s+following)", _I)
_LOOKAHEAD_CHARS = 900  # how far past "I impose the following penalty:" the amount may be stated
_AGGREGATE = re.compile(r"\b(?:aggregat\w+|in\s+total|total(?:ling)?|cumulative)\b", _I)
_RESTRAINT = re.compile(
    r"\b(?:restrain\w*|prohibit\w*|debar\w*)\b[^.]{0,160}?"
    r"\b(?:securities\s+market|dealing\s+in\s+securities|buying,\s*selling|access\w*\s+the\s+securities)",
    _I,
)
_DIRECTIVE = re.compile(r"\bhereby\b|\bdirected\b|\bshall\b", _I)
_DURATION = re.compile(r"\bfor\s+a\s+period\s+of\s+([^,;.]+?)(?=\s+from\b|[,;.]|$)", _I)
_SETTLEMENT = re.compile(r"\bsettlement\s+amount\b|\bsettle\w*\s+[^.]{0,40}\bpay\w*", _I)
_SETTLE_ACTION = re.compile(r"\b(?:pay|paid|remit\w*|recommended|proposed)\b", _I)

_ADMITTED = re.compile(
    r"\b(?:is|are|be|hereby|stands?)\s+(?:hereby\s+)?admitted\b|\badmit(?:s|ting)?\b[^.]{0,80}\b"
    r"(?:CIRP|Corporate\s+Insolvency|petition|application)\b",
    _I,
)
_ADMIT_CONTEXT = re.compile(
    r"\b(?:CIRP|Corporate\s+Debtor|Corporate\s+Insolvency|petition|application|CP\b|IB\b)", _I
)
_SECTION = re.compile(r"\b(?:section|sec\.|u/s\.?)\s*(7|9|10)\b", _I)
_APPLICANTS = {
    "financial creditor": re.compile(r"\bfinancial\s+creditors?\b", _I),
    "operational creditor": re.compile(r"\boperational\s+creditors?\b", _I),
    "corporate applicant": re.compile(r"\bcorporate\s+applicants?\b", _I),
}

_AUTHORITY = {
    "SEBI adjudication order": "Adjudicating Officer",
    "SEBI whole-time member order": "Whole-time Member",
}


@dataclass(slots=True)
class EventDraft:
    type: EventType
    trigger: Span
    arguments: dict[str, str] = field(default_factory=dict)
    amount_inr: Decimal | None = None
    event_date: date | None = None
    schema_valid: bool = True


@dataclass(frozen=True, slots=True)
class _Sentence:
    span: Span
    text: str
    position: float  # 0 at the start of the document, 1 at the end


def _sentences(text: str, spans: list[Span]) -> list[_Sentence]:
    n = max(len(text), 1)
    return [_Sentence(s, s.slice(text), s.start / n) for s in spans]


def _amount(sentence: str) -> tuple[Decimal | None, list[Decimal]]:
    """The one amount a sentence fixes, or None when it states several without a total."""
    values = [a.inr for a in find_amounts(sentence)]
    if not values:
        return None, []
    if len(values) == 1:
        return values[0], values
    if _AGGREGATE.search(sentence):
        return values[-1], values  # "... aggregating to Rs. 5,00,000/-"
    return None, values


def _provisions(sentence: str) -> str:
    seen: list[str] = []
    for ref in find_statutes(sentence):
        prov = re.sub(r"^u/s\.?\s*", "Section ", ref.provision, flags=_I)
        label = f"{prov[:1].upper()}{prov[1:]} of {ref.instrument}"
        if label not in seen:
            seen.append(label)
    return "; ".join(seen)


def _pick_penalty(sents: list[_Sentence]) -> tuple[_Sentence, str] | None:
    """The sentence that imposes the penalty, and the text its amount is read from.

    Usually that is the sentence itself. Orders that write "I hereby impose the following penalty:"
    state the amount in the lines (or table) after it, so those are read as well.
    """
    best: tuple[int, int] | None = None
    for i, s in enumerate(sents):
        if not _PENALTY.search(s.text):
            continue
        imposes = bool(_HEREBY_IMPOSE.search(s.text))
        if not find_amounts(s.text) and not (imposes and _FOLLOWING.search(s.text)):
            continue
        score = (
            3 * imposes
            + (s.position > 0.6)
            + bool(re.search(r"\bon\s+the\s+noticee|\bin\s+respect\s+of|\bshall\s+pay", s.text, _I))
        )
        if score >= 3 and (best is None or score >= best[0]):  # a later sentence wins a tie
            best = (score, i)
    if best is None:
        return None
    trigger = sents[best[1]]
    if find_amounts(trigger.text):
        return trigger, trigger.text
    after = [
        n.text
        for n in sents[best[1] + 1 : best[1] + 7]
        if n.span.start - trigger.span.end <= _LOOKAHEAD_CHARS
    ]
    return trigger, " ".join(after)


def _sebi_events(doc_type: str | None, sents: list[_Sentence]) -> list[EventDraft]:
    authority = _AUTHORITY.get(doc_type or "")

    picked = _pick_penalty(sents)
    if picked is not None and doc_type != "SEBI settlement order":
        penalty, read_from = picked
        amount, all_amounts = _amount(read_from)
        args = {"action": "penalty"}
        if len(all_amounts) > 1 and amount is None:
            args["amounts_stated"] = ", ".join(f"{a:f}" for a in all_amounts)
        return [_sebi_draft(penalty, args, amount, authority)]

    if doc_type == "SEBI settlement order":
        candidates = [s for s in sents if _SETTLEMENT.search(s.text) and find_amounts(s.text)]
        preferred = [s for s in candidates if _SETTLE_ACTION.search(s.text)] or candidates
        if preferred:
            trigger = preferred[0]
            amount, all_amounts = _amount(trigger.text)
            args = {"action": "settlement"}
            if len(all_amounts) > 1 and amount is None:
                args["amounts_stated"] = ", ".join(f"{a:f}" for a in all_amounts)
            return [_sebi_draft(trigger, args, amount, authority)]
        return []

    restraints = [s for s in sents if _RESTRAINT.search(s.text)]
    directed = [s for s in restraints if _DIRECTIVE.search(s.text)]
    if directed:
        hereby = [s for s in directed if re.search(r"\bhereby\b", s.text, _I)]
        trigger = (hereby or directed)[0]
        args = {"action": "restraint"}
        if m := _DURATION.search(trigger.text):
            args["duration"] = m.group(1).strip()
        return [_sebi_draft(trigger, args, None, authority)]
    return []


def _sebi_draft(
    trigger: _Sentence, args: dict[str, str], amount: Decimal | None, authority: str | None
) -> EventDraft:
    if provisions := _provisions(trigger.text):
        args["provisions"] = provisions
    if authority:
        args["authority"] = authority
    return EventDraft(EventType.SEBI_PENALTY, trigger.span, args, amount)


def _nclt_events(text: str, sents: list[_Sentence]) -> list[EventDraft]:
    candidates = [s for s in sents if _ADMITTED.search(s.text) and _ADMIT_CONTEXT.search(s.text)]
    if not candidates:
        return []
    trigger = max(candidates, key=lambda s: (s.position > 0.5, "Corporate Debtor" in s.text, s.position))
    args: dict[str, str] = {}
    if m := _SECTION.search(text):
        args["section"] = f"Section {m.group(1)}"
    counts = Counter({name: len(rx.findall(text)) for name, rx in _APPLICANTS.items()})
    top = counts.most_common(2)
    if top[0][1] > 0 and (len(top) == 1 or top[0][1] > top[1][1]):
        args["applicant_type"] = top[0][0]
    args["moratorium"] = "true" if re.search(r"\bmoratorium\b", text, _I) else "false"
    return [EventDraft(EventType.NCLT_ADMISSION, trigger.span, args)]


def extract_events(
    *,
    source_kind: str,
    doc_type: str | None,
    text: str,
    sentence_spans: list[Span],
    published_at: date | None,
) -> list[EventDraft]:
    sents = _sentences(text, sentence_spans)
    if source_kind == "SEBI":
        drafts = _sebi_events(doc_type, sents)
    elif source_kind == "NCLT":
        drafts = _nclt_events(text, sents)
    else:
        drafts = []
    for d in drafts:
        d.event_date = published_at
        d.schema_valid = validate_arguments(d.type, _typed_arguments(d))
    return drafts


def _typed_arguments(draft: EventDraft) -> dict[str, object]:
    """Arguments as the Pydantic model wants them (lists, numbers, booleans)."""
    out: dict[str, object] = {}
    for key, value in draft.arguments.items():
        if key == "provisions":
            out[key] = [p for p in value.split("; ") if p]
        elif key == "moratorium":
            out[key] = value == "true"
        elif key == "amounts_stated":
            continue  # kept in the stored arguments for the reader, not part of the typed schema
        else:
            out[key] = value
    if draft.amount_inr is not None:
        out["amount_inr"] = draft.amount_inr
    return out
