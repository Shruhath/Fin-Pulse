import json
from decimal import Decimal

import pytest

from finpulse.events.llm import (
    EVENT_RESPONSE_SCHEMA,
    SYSTEM,
    build_prompt,
    extract_llm_events,
    normalise_arguments,
    parse_events,
)
from finpulse.events.taxonomy import EventType, validate_arguments
from finpulse.llm.client import LlmError, LlmUnavailable, Reply


class FakeLlm:
    """Returns queued replies and records what it was asked."""

    def __init__(self, *texts):
        self.texts = list(texts)
        self.calls = []

    def chat(self, model, system, user, *, schema=None, num_predict=1024):
        self.calls.append({"model": model, "system": system, "user": user, "schema": schema})
        text = self.texts.pop(0)
        if isinstance(text, Exception):
            raise text
        return Reply(text=text, model=model, prompt_tokens=100, completion_tokens=20, seconds=1.5)


SHOWN = [
    (3, "I hereby impose a penalty of Rs. 4,00,000/- on the Noticee."),
    (9, "The matter is disposed of."),
]


def _event(**over):
    base = {
        "trigger_sentence_id": 3,
        "type": "SEBI Penalty",
        "entity": "Raga Securities",
        "arguments": {
            "action": "penalty",
            "amount_inr": "Rs. 4,00,000/-",
            "provisions": "Section 15HB of SEBI Act",
        },
    }
    return {**base, **over}


def test_prompt_lists_every_type_the_entities_and_numbered_sentences():
    prompt = build_prompt(
        title="Order in the matter of Raga", source="SEBI", doc_type="SEBI adjudication order",
        entities=["Raga Securities Ltd"], shown=SHOWN,
    )  # fmt: skip
    assert all(t.value in prompt for t in EventType)
    assert "action (exactly one of: penalty, restraint, settlement)" in prompt
    assert "[S3] I hereby impose" in prompt and "[S9] The matter" in prompt
    assert "Raga Securities Ltd" in prompt and "SEBI (SEBI adjudication order)" in prompt
    assert "never infer" in SYSTEM and EVENT_RESPONSE_SCHEMA["required"] == ["events"]


def test_a_valid_event_is_normalised_and_typed():
    (d,) = parse_events({"events": [_event()]}, {3, 9}, {})
    assert d.type is EventType.SEBI_PENALTY and d.trigger_sentence == 3
    assert d.amount_inr == Decimal(400000)
    assert d.arguments["action"] == "penalty" and d.schema_valid
    assert d.entity_name == "Raga Securities"


def test_unknown_names_are_dropped_and_bad_values_fail_validation_but_the_event_stays():
    stored, typed, amount = normalise_arguments(
        EventType.SEBI_PENALTY, {"action": "penalty", "colour": "red", "amount_inr": "a lot", "duration": ""}
    )
    assert "colour" not in stored and "duration" not in stored
    assert amount is None and typed["amount_inr"] == "a lot"
    (d,) = parse_events({"events": [_event(arguments={"action": "fine"})]}, {3}, {})
    assert d.schema_valid is False and d.arguments == {"action": "fine"}


def test_events_pointing_at_sentences_that_were_not_shown_are_dropped_and_counted():
    dropped = {}
    drafts = parse_events(
        {"events": [_event(trigger_sentence_id=77), _event(type="Mystery Event"), {"nonsense": 1}, _event()]},
        {3, 9},
        dropped,
    )
    assert len(drafts) == 1
    assert dropped == {"trigger sentence not shown": 1, "unknown type or bad trigger": 2}


def test_indian_dates_and_lists_are_converted_for_the_typed_model():
    stored, typed, _ = normalise_arguments(
        EventType.AUDITOR_RESIGNATION, {"auditor": "XYZ & Co", "effective_date": "12th March, 2024"}
    )
    assert str(typed["effective_date"]) == "2024-03-12" and stored["auditor"] == "XYZ & Co"
    _, typed, _ = normalise_arguments(EventType.SEBI_PENALTY, {"provisions": "Section 15HB; Section 15A(b)"})
    assert typed["provisions"] == ["Section 15HB", "Section 15A(b)"]


def test_a_bad_first_answer_is_retried_with_the_error_and_the_next_answer_used():
    llm = FakeLlm("not json at all", json.dumps({"events": [_event()]}))
    result = extract_llm_events(
        llm, "qwen", title="t", source="SEBI", doc_type=None, entities=[], shown=SHOWN
    )
    assert result.attempts == 2 and len(result.drafts) == 1
    assert "rejected" in llm.calls[1]["user"] and "invalid JSON" in llm.calls[1]["user"]
    assert llm.calls[0]["schema"] == EVENT_RESPONSE_SCHEMA
    assert result.prompt_tokens == 200 and result.completion_tokens == 40


def test_three_bad_answers_raise_and_an_unavailable_model_propagates():
    with pytest.raises(LlmError, match="after 3 attempts"):
        extract_llm_events(
            FakeLlm("x", "y", "z"), "qwen", title="t", source="SEBI", doc_type=None, entities=[], shown=SHOWN
        )
    with pytest.raises(LlmUnavailable):
        extract_llm_events(
            FakeLlm(LlmUnavailable("down")),
            "qwen",
            title="t",
            source="SEBI",
            doc_type=None,
            entities=[],
            shown=SHOWN,
        )


def test_an_empty_list_is_a_valid_answer():
    result = extract_llm_events(
        FakeLlm('{"events": []}'), "qwen", title="t", source="SEBI", doc_type=None, entities=[], shown=SHOWN
    )
    assert result.drafts == [] and result.attempts == 1


def test_enum_arguments_are_matched_ignoring_case_and_moratorium_text_counts_as_yes():
    stored, typed, _ = normalise_arguments(
        EventType.NCLT_ADMISSION,
        {
            "applicant_type": "Operational Creditor",
            "moratorium": "from the date of the order",
            "section": "9",
        },
    )
    assert typed["applicant_type"] == "operational creditor" and typed["moratorium"] is True
    assert stored["applicant_type"] == "Operational Creditor"  # what the model said is kept as written
    assert validate_arguments(EventType.NCLT_ADMISSION, typed)
    assert normalise_arguments(EventType.NCLT_ADMISSION, {"moratorium": "No"})[1]["moratorium"] is False
    _, bad, _ = normalise_arguments(EventType.NCLT_ADMISSION, {"applicant_type": "the bank"})
    assert bad["applicant_type"] == "the bank" and not validate_arguments(EventType.NCLT_ADMISSION, bad)


@pytest.mark.parametrize(
    ("phrase", "value"),
    [
        ("impose a penalty", "penalty"),
        ("levied monetary penalty", "penalty"),
        ("restrained from the market", "restraint"),
        ("debarred for two years", "restraint"),
        ("accepted the settlement", "settlement"),
    ],
)  # fmt: skip
def test_phrases_for_the_action_map_to_one_value_and_unclear_ones_stay_invalid(phrase, value):
    _, typed, _ = normalise_arguments(EventType.SEBI_PENALTY, {"action": phrase})
    assert typed["action"] == value
    _, mixed, _ = normalise_arguments(EventType.SEBI_PENALTY, {"action": "penalty and restraint"})
    assert mixed["action"] == "penalty and restraint" and not validate_arguments(
        EventType.SEBI_PENALTY, mixed
    )


def test_a_creditor_name_in_applicant_type_is_not_guessed():
    _, typed, _ = normalise_arguments(EventType.NCLT_ADMISSION, {"applicant_type": "State Bank of India"})
    assert typed["applicant_type"] == "State Bank of India"
    assert (
        normalise_arguments(EventType.NCLT_ADMISSION, {"applicant_type": "Financial Creditor/Applicant"})[1][
            "applicant_type"
        ]
        == "financial creditor"
    )
