"""LLM event extraction (Qwen 2.5 7B through Ollama).

The model sees the title, the entities already resolved for the document, the 16-type taxonomy
with one-line definitions, and the numbered sentences chosen by `summarize.prune`. It returns the
events it finds as JSON, each pointing at the sentence that triggers it. Decoding is constrained
to a JSON schema; the arguments are then validated against the typed model of the event's type.
An event is kept even when its arguments fail that validation (`schema_valid` is false), because
schema validity is itself a reported metric; an event whose trigger sentence was never shown, or
whose type is unknown, is dropped and counted.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from finpulse.llm.client import Llm, LlmError
from finpulse.preprocess.normalize import find_amounts, find_dates

from .taxonomy import DEFINITIONS, EventType, argument_choices, argument_fields, validate_arguments

log = logging.getLogger(__name__)

PROMPT_VERSION = "events-v2"
MAX_ATTEMPTS = 3  # the first try and two retries

EVENT_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "events": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "trigger_sentence_id": {"type": "integer"},
                    "type": {"type": "string", "enum": [t.value for t in EventType]},
                    "entity": {"type": ["string", "null"]},
                    "arguments": {
                        "type": "object",
                        "additionalProperties": {"type": ["string", "number", "boolean", "null"]},
                    },
                },
                "required": ["trigger_sentence_id", "type", "entity", "arguments"],
            },
        }
    },
    "required": ["events"],
}

SYSTEM = (
    "You extract corporate and regulatory events from Indian financial disclosures. "
    "Report only events the text states explicitly; never infer or invent. "
    "Each event cites the number of the single sentence that states it. "
    "Copy amounts and names as written. Leave an argument out when the text does not give it. "
    "If the passage reports no event of the listed types, return an empty list."
)


@dataclass(slots=True)
class LlmEventDraft:
    type: EventType
    trigger_sentence: int  # the stored sentence index, not a position in the prompt
    entity_name: str | None
    arguments: dict[str, str]
    amount_inr: Decimal | None
    schema_valid: bool


@dataclass(slots=True)
class ExtractionResult:
    drafts: list[LlmEventDraft] = field(default_factory=list)
    dropped: dict[str, int] = field(default_factory=dict)
    attempts: int = 1
    prompt_tokens: int = 0
    completion_tokens: int = 0
    seconds: float = 0.0


def _argument_spec(event_type: EventType, key: str) -> str:
    choices = argument_choices(event_type, key)
    return f"{key} (exactly one of: {', '.join(choices)})" if choices else key


def taxonomy_text() -> str:
    lines = []
    for t in EventType:
        args = ", ".join(_argument_spec(t, k) for k in argument_fields(t))
        lines.append(f"- {t.value}: {DEFINITIONS[t]} Arguments: {args}.")
    return "\n".join(lines)


def build_prompt(
    *, title: str, source: str, doc_type: str | None, entities: list[str], shown: list[tuple[int, str]]
) -> str:
    named = "; ".join(entities) if entities else "(none resolved)"
    sentences = "\n".join(f"[S{i}] {text}" for i, text in shown)
    return (
        f"Document: {title}\nSource: {source}{f' ({doc_type})' if doc_type else ''}\n"
        f"Entities in this document: {named}\n\n"
        f"Event types and their arguments:\n{taxonomy_text()}\n\n"
        f"Sentences:\n{sentences}\n\n"
        'Return JSON: {"events": [{"trigger_sentence_id": <number from [S..]>, "type": <one of the types>, '
        '"entity": <the company or party the event is about, as written>, "arguments": {<name>: <value>}}]}'
    )


def _amount(value: Any) -> Decimal | None:
    text = str(value).strip()
    if found := find_amounts(text if re.search(r"rs|inr|₹|rupee", text, re.IGNORECASE) else f"Rs. {text}"):
        return found[0].inr
    try:
        return Decimal(text.replace(",", ""))
    except InvalidOperation:
        return None


# Models often answer an enum argument with a phrase ("impose a penalty"). A phrase that contains exactly one
# of these keywords is mapped to its value; anything else stays as written and fails validation.
ENUM_HINTS: dict[str, list[tuple[str, str]]] = {
    "action": [
        ("penalt", "penalty"),
        ("restrain", "restraint"),
        ("debar", "restraint"),
        ("prohibit", "restraint"),
        ("settle", "settlement"),
    ],
    "applicant_type": [
        ("operational", "operational creditor"),
        ("financial", "financial creditor"),
        ("corporate applicant", "corporate applicant"),
    ],
    "direction": [
        ("rais", "raise"),
        ("increas", "raise"),
        ("cut", "cut"),
        ("lower", "cut"),
        ("reduc", "cut"),
        ("withdr", "withdraw"),
        ("maintain", "maintain"),
        ("reaffirm", "maintain"),
    ],
}


def _enum_value(key: str, value: object, choices: list[str]) -> str:
    text = str(value).strip().lower()
    if text in choices:
        return text
    found = {target for word, target in ENUM_HINTS.get(key, []) if word in text}
    return found.pop() if len(found) == 1 else str(value)


def normalise_arguments(
    event_type: EventType, raw: dict[str, Any]
) -> tuple[dict[str, str], dict[str, Any], Decimal | None]:
    """(arguments as stored, arguments as the typed model wants them, the event's amount).

    Unknown argument names are dropped. Amounts and dates written the Indian way are converted.
    """
    allowed = set(argument_fields(event_type))
    stored: dict[str, str] = {}
    typed: dict[str, Any] = {}
    amount: Decimal | None = None
    for key, value in raw.items():
        if key not in allowed or value is None or value == "":
            continue
        stored[key] = str(value)
        if key.endswith("_inr"):
            parsed = _amount(value)
            if parsed is not None:
                typed[key] = parsed
                amount = amount or parsed
            else:
                typed[key] = str(value)  # fails validation: the model did not give a number
        elif key.endswith("_date"):
            dates = find_dates(str(value))
            typed[key] = dates[0].value if dates else str(value)
        elif key == "provisions":
            typed[key] = [p.strip() for p in re.split(r"[;|]", str(value)) if p.strip()]
        elif key == "moratorium":
            # a bare yes/no, or a description of the moratorium: only an explicit no means there is none
            typed[key] = str(value).strip().lower() not in {
                "false",
                "no",
                "0",
                "none",
                "n/a",
                "not applicable",
            }
        elif key == "shares":
            try:
                typed[key] = int(str(value).replace(",", ""))
            except ValueError:
                typed[key] = str(value)
        elif (choices := argument_choices(event_type, key)) is not None:
            typed[key] = _enum_value(key, value, choices)  # "Operational Creditor" -> "operational creditor"
        else:
            typed[key] = value
    return stored, typed, amount


def parse_events(data: Any, shown_ids: set[int], dropped: dict[str, int]) -> list[LlmEventDraft]:
    if not isinstance(data, dict) or not isinstance(data.get("events"), list):
        raise LlmError('the JSON has no "events" list')
    drafts: list[LlmEventDraft] = []
    for item in data["events"]:
        try:
            etype = EventType(item["type"])
            sentence = int(item["trigger_sentence_id"])
        except (KeyError, ValueError, TypeError):
            dropped["unknown type or bad trigger"] = dropped.get("unknown type or bad trigger", 0) + 1
            continue
        if sentence not in shown_ids:
            dropped["trigger sentence not shown"] = dropped.get("trigger sentence not shown", 0) + 1
            continue
        args = item.get("arguments") if isinstance(item.get("arguments"), dict) else {}
        stored, typed, amount = normalise_arguments(etype, args)
        entity = item.get("entity")
        drafts.append(
            LlmEventDraft(
                type=etype,
                trigger_sentence=sentence,
                entity_name=entity.strip() if isinstance(entity, str) and entity.strip() else None,
                arguments=stored,
                amount_inr=amount,
                schema_valid=validate_arguments(etype, typed),
            )
        )
    return drafts


def extract_llm_events(
    llm: Llm,
    model: str,
    *,
    title: str,
    source: str,
    doc_type: str | None,
    entities: list[str],
    shown: list[tuple[int, str]],
) -> ExtractionResult:
    """One document. Retries with the error message when the reply is not usable JSON."""
    result = ExtractionResult()
    prompt = build_prompt(title=title, source=source, doc_type=doc_type, entities=entities, shown=shown)
    shown_ids = {i for i, _ in shown}
    last_error = ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        user = (
            prompt
            if not last_error
            else f"{prompt}\n\nYour previous answer was rejected: {last_error}. Answer again."
        )
        reply = llm.chat(model, SYSTEM, user, schema=EVENT_RESPONSE_SCHEMA, num_predict=1500)
        result.attempts = attempt
        result.prompt_tokens += reply.prompt_tokens
        result.completion_tokens += reply.completion_tokens
        result.seconds += reply.seconds
        try:
            result.dropped = {}
            result.drafts = parse_events(reply.json(), shown_ids, result.dropped)
            return result
        except LlmError as exc:
            last_error = str(exc)
            log.warning("event extraction attempt %d failed: %s", attempt, exc)
    raise LlmError(f"no usable answer after {MAX_ATTEMPTS} attempts: {last_error}")
