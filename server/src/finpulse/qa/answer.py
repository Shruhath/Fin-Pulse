"""Answer a question from retrieved sentences with the local Llama model.

The model writes one to four short claims and names, for each, the numbered sentences it rests on; it
may also say the sentences do not answer the question. The claims are checked afterwards by NLI
(`pipeline/ask.py`), so an answer the evidence does not support is shown as unverified or contradicted.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from finpulse.llm.client import Llm, LlmError
from finpulse.summarize.llm import ClaimDraft, parse_claims

from .retrieve import Passage

log = logging.getLogger(__name__)

PROMPT_VERSION = "qa-v1"
MAX_ATTEMPTS = 3

ANSWER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "answerable": {"type": "boolean"},
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "sources": {"type": "array", "items": {"type": "integer"}},
                },
                "required": ["text", "sources"],
            },
        },
    },
    "required": ["answerable", "claims"],
}

SYSTEM = (
    "You answer questions about Indian regulatory and corporate disclosures for analysts. "
    "Use ONLY the numbered evidence sentences you are given; each shows the document it comes from. "
    "If the evidence does not answer the question, set answerable to false and write no claims; "
    "never write a claim that says something is not mentioned. "
    "Otherwise write one to four short claims that answer the question directly, each a single factual "
    "sentence that names the company it is about. "
    "For every claim, list the numbers of the evidence sentences that state it. "
    "Copy names, amounts and dates exactly as written. "
    "Never use outside knowledge, and never guess."
)


@dataclass(slots=True)
class AnswerResult:
    answerable: bool
    claims: list[ClaimDraft] = field(default_factory=list)
    attempts: int = 1
    prompt_tokens: int = 0
    completion_tokens: int = 0
    seconds: float = 0.0
    dropped_sources: int = 0


# a "claim" that only reports what the evidence lacks is a refusal in disguise
_ABSENCE = re.compile(
    r"\b(?:not|no|never|cannot|n't)\b[^.]{0,50}\b(?:specified|mentioned|provided|stated|given|available|"
    r"included|contain|say|indicate|address|answer)|\bno (?:information|evidence|mention|data)\b",
    re.IGNORECASE,
)


def build_prompt(question: str, passages: list[Passage]) -> str:
    # the document title says whom a sentence like "The Noticee shall pay" is about; the publication date
    # is left out because a model reads it as the date of the event
    lines = "\n".join(f"[S{p.sentence_id}] ({p.title}) {p.text}" for p in passages)
    return (
        f"Question: {question}\n\nEvidence:\n{lines}\n\n"
        'Return JSON: {"answerable": <true or false>, "claims": [{"text": <one sentence>, '
        '"sources": [<evidence numbers>]}]}'
    )


def parse_answer(data: Any, shown_ids: set[int]) -> tuple[bool, list[ClaimDraft], int]:
    if not isinstance(data, dict):
        raise LlmError("the JSON is not an object")
    if data.get("answerable") is False:
        return False, [], 0
    claims, dropped = parse_claims(data, shown_ids)
    claims = [c for c in claims if not _ABSENCE.search(c.text)]
    if not claims:
        return False, [], dropped
    return True, claims, dropped


def answer(llm: Llm, model: str, question: str, passages: list[Passage]) -> AnswerResult:
    prompt = build_prompt(question, passages)
    shown_ids = {p.sentence_id for p in passages}
    result = AnswerResult(answerable=False)
    last_error = ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        user = (
            prompt
            if not last_error
            else f"{prompt}\n\nYour previous answer was rejected: {last_error}. Answer again."
        )
        reply = llm.chat(model, SYSTEM, user, schema=ANSWER_SCHEMA, num_predict=700)
        result.attempts = attempt
        result.prompt_tokens += reply.prompt_tokens
        result.completion_tokens += reply.completion_tokens
        result.seconds += reply.seconds
        try:
            result.answerable, result.claims, result.dropped_sources = parse_answer(reply.json(), shown_ids)
            return result
        except LlmError as exc:
            last_error = str(exc)
            log.warning("answer attempt %d failed: %s", attempt, exc)
    raise LlmError(f"no usable answer after {MAX_ATTEMPTS} attempts: {last_error}")
