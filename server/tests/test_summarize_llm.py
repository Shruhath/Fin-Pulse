import json

import pytest

from finpulse.llm.client import LlmError, Reply
from finpulse.summarize.llm import SUMMARY_SCHEMA, SYSTEM, build_prompt, parse_claims, summarise

EVIDENCE = [
    (101, "SEBI imposed a penalty of Rs. 4,00,000 on Raga Securities."),
    (205, "The penalty was imposed under section 15HB of the SEBI Act."),
    (310, "The noticee was a registered stock broker."),
]


class FakeLlm:
    def __init__(self, *texts):
        self.texts, self.calls = list(texts), []

    def chat(self, model, system, user, *, schema=None, num_predict=1024):
        self.calls.append((system, user, schema))
        return Reply(self.texts.pop(0), model, 500, 80, 3.0)


def test_prompt_numbers_the_evidence_by_stored_sentence_id():
    prompt = build_prompt(subject="Raga Securities", scope="entity", evidence=EVIDENCE)
    assert "[S101] SEBI imposed" in prompt and "[S310] The noticee" in prompt
    assert "what the documents say about the company" in prompt
    assert "ONLY" in SYSTEM and SUMMARY_SCHEMA["required"] == ["claims"]


def test_citations_to_sentences_never_shown_are_dropped_and_counted():
    data = {"claims": [{"text": "SEBI fined Raga Rs. 4,00,000.", "sources": [101, 999, 101, "205"]}]}
    claims, dropped = parse_claims(data, {101, 205, 310})
    assert claims[0].sources == [101, 205] and dropped == 1


def test_inline_citation_markers_are_stripped_from_the_claim_text():
    data = {
        "claims": [{"text": "SEBI fined Raga [S101][S205].", "sources": [101]}, {"text": "  ", "sources": []}]
    }
    claims, _ = parse_claims(data, {101, 205})
    assert [c.text for c in claims] == ["SEBI fined Raga."]


def test_a_claim_without_sources_is_kept_for_the_verifier_to_judge():
    claims, _ = parse_claims({"claims": [{"text": "It was a big fine.", "sources": []}]}, {1})
    assert claims[0].sources == []


def test_at_most_five_claims_are_kept():
    data = {"claims": [{"text": f"Claim {i}.", "sources": []} for i in range(9)]}
    assert len(parse_claims(data, set())[0]) == 5


def test_retry_with_the_reason_then_use_the_good_answer():
    good = json.dumps({"claims": [{"text": "SEBI fined Raga.", "sources": [101]}]})
    llm = FakeLlm("nope", good)
    result = summarise(llm, "llama", subject="Raga", scope="document", evidence=EVIDENCE)
    assert result.attempts == 2 and result.claims[0].sources == [101]
    assert "rejected" in llm.calls[1][1] and llm.calls[0][2] == SUMMARY_SCHEMA
    assert result.prompt_tokens == 1000 and result.seconds == pytest.approx(6.0)


def test_no_claims_three_times_raises():
    empty = json.dumps({"claims": []})
    with pytest.raises(LlmError, match="after 3 attempts"):
        summarise(FakeLlm(empty, empty, empty), "llama", subject="x", scope="document", evidence=EVIDENCE)
