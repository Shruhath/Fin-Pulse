"""Grounded summaries with the local Llama model.

The model writes three to five claims and names, for each, the numbered evidence sentences it
rests on. It is told to use nothing else. The claims are stored as written and judged afterwards
by retrieval plus NLI (`verify/`), so a claim the evidence does not support is shown as
unverified or contradicted, never silently dropped.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from finpulse.llm.client import Llm, LlmError

log = logging.getLogger(__name__)

PROMPT_VERSION = "summary-v1"
MAX_ATTEMPTS = 3
MAX_CLAIMS = 5

SUMMARY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
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
        }
    },
    "required": ["claims"],
}

SYSTEM = (
    "You summarise Indian financial disclosures for analysts. "
    "Use ONLY the numbered evidence sentences you are given. "
    "Write three to five short claims, each a single factual sentence. "
    "For every claim, list the numbers of the evidence sentences that state it. "
    "Copy amounts, dates and names exactly as written. "
    "Do not add background, opinion or anything the evidence does not say. "
    "If the evidence is too thin for a claim, write fewer claims."
)


@dataclass(slots=True)
class ClaimDraft:
    text: str
    sources: list[int]  # evidence sentence ids that were actually shown


@dataclass(slots=True)
class SummaryResult:
    claims: list[ClaimDraft] = field(default_factory=list)
    attempts: int = 1
    prompt_tokens: int = 0
    completion_tokens: int = 0
    seconds: float = 0.0
    dropped_sources: int = 0


def build_prompt(*, subject: str, scope: str, evidence: list[tuple[int, str]]) -> str:
    what = "the document" if scope == "document" else "what the documents say about the company"
    lines = "\n".join(f"[S{sid}] {text}" for sid, text in evidence)
    return (
        f"Subject: {subject}\nSummarise {what} from this evidence only.\n\nEvidence:\n{lines}\n\n"
        'Return JSON: {"claims": [{"text": <one sentence>, "sources": [<evidence numbers>]}]}'
    )


def parse_claims(data: Any, shown_ids: set[int]) -> tuple[list[ClaimDraft], int]:
    if not isinstance(data, dict) or not isinstance(data.get("claims"), list):
        raise LlmError('the JSON has no "claims" list')
    claims: list[ClaimDraft] = []
    dropped = 0
    for item in data["claims"][:MAX_CLAIMS]:
        text = (
            re.sub(r"\s*\[S?\d+(?:\s*,\s*S?\d+)*\]", "", str(item.get("text", ""))).strip()
            if isinstance(item, dict)
            else ""
        )
        if not text:
            continue
        raw = item.get("sources", [])
        ids: list[int] = []
        for s in raw if isinstance(raw, list) else []:
            try:
                sid = int(s)
            except (TypeError, ValueError):
                dropped += 1
                continue
            if sid in shown_ids and sid not in ids:
                ids.append(sid)
            elif sid not in shown_ids:
                dropped += 1  # a citation to a sentence the model was never shown
        claims.append(ClaimDraft(text=text, sources=ids))
    if not claims:
        raise LlmError("the summary has no claims")
    return claims, dropped


def summarise(
    llm: Llm, model: str, *, subject: str, scope: str, evidence: list[tuple[int, str]]
) -> SummaryResult:
    prompt = build_prompt(subject=subject, scope=scope, evidence=evidence)
    shown_ids = {sid for sid, _ in evidence}
    result = SummaryResult()
    last_error = ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        user = (
            prompt
            if not last_error
            else f"{prompt}\n\nYour previous answer was rejected: {last_error}. Answer again."
        )
        reply = llm.chat(model, SYSTEM, user, schema=SUMMARY_SCHEMA, num_predict=700)
        result.attempts = attempt
        result.prompt_tokens += reply.prompt_tokens
        result.completion_tokens += reply.completion_tokens
        result.seconds += reply.seconds
        try:
            result.claims, result.dropped_sources = parse_claims(reply.json(), shown_ids)
            return result
        except LlmError as exc:
            last_error = str(exc)
            log.warning("summary attempt %d failed: %s", attempt, exc)
    raise LlmError(f"no usable summary after {MAX_ATTEMPTS} attempts: {last_error}")
