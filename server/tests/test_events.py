from datetime import date
from decimal import Decimal

import pytest

from finpulse.events.headline import headline
from finpulse.events.rules import extract_events
from finpulse.events.taxonomy import EVENT_GROUP, EventType, validate_arguments
from finpulse.preprocess.sentences import split_sentences


def run(kind, doc_type, text, published=date(2024, 5, 2)):
    return extract_events(
        source_kind=kind,
        doc_type=doc_type,
        text=text,
        sentence_spans=split_sentences(text),
        published_at=published,
    )


def test_every_type_has_a_group_and_the_taxonomy_has_sixteen():
    assert len(EventType) == 16
    assert set(EVENT_GROUP) == set(EventType)


def test_argument_models_reject_unknown_fields_and_bad_enums():
    assert validate_arguments(EventType.SEBI_PENALTY, {"action": "penalty", "amount_inr": Decimal(5)})
    assert not validate_arguments(EventType.SEBI_PENALTY, {"action": "fine"})
    assert not validate_arguments(EventType.SEBI_PENALTY, {"colour": "red"})
    assert validate_arguments(EventType.REGULAR_DIVIDEND, {"per_share_inr": Decimal("2.5")})


AO = (
    "In the matter of Raga Securities and Finance Private Limited.\n\n"
    "The noticee was found to have violated the code of conduct.\n\n"
    "20. In exercise of the powers conferred under section 15 I of the SEBI Act and Rule 5 of the AO Rules, "
    "I hereby imposed a penalty of Rs. 4,00,000/- (Rupees Four Lakhs only) on the Noticee viz. Raga "
    "Securities and Finance Private Limited under section 15HB of SEBI Act for the violation of the "
    "Brokers Regulations.\n\n"
    "21. The penalty shall be paid within 45 days."
)


def test_adjudication_order_yields_one_penalty_with_amount_and_provision():
    (ev,) = run("SEBI", "SEBI adjudication order", AO)
    assert ev.type is EventType.SEBI_PENALTY
    assert ev.amount_inr == Decimal(400000)
    assert ev.arguments["action"] == "penalty"
    assert ev.arguments["authority"] == "Adjudicating Officer"
    assert "Section 15HB of SEBI Act" in ev.arguments["provisions"]
    assert ev.event_date == date(2024, 5, 2)
    assert ev.schema_valid
    assert "hereby imposed a penalty" in ev.trigger.slice(AO)


def test_trigger_is_an_exact_slice_of_the_text():
    (ev,) = run("SEBI", "SEBI adjudication order", AO)
    assert AO[ev.trigger.start : ev.trigger.end].startswith("20. In exercise")


def test_several_amounts_without_a_total_leave_the_amount_unset():
    text = (
        "I hereby impose a penalty of Rs. 2,00,000/- under section 15A(b) and Rs. 3,00,000/- "
        "under section 15HB of the SEBI Act on the Noticee."
    )
    (ev,) = run("SEBI", "SEBI adjudication order", text)
    assert ev.amount_inr is None
    assert ev.arguments["amounts_stated"] == "200000, 300000"


def test_several_amounts_with_an_aggregate_take_the_total():
    text = (
        "I impose a penalty of Rs. 2,00,000/- under section 15A(c) and Rs. 1,00,000/- under section 15HB "
        "of the SEBI Act in respect of LKP Securities Limited, aggregating to Rs. 3,00,000/-."
    )
    (ev,) = run("SEBI", "SEBI adjudication order", text)
    assert ev.amount_inr == Decimal(300000)


def test_a_recital_of_an_earlier_penalty_is_not_the_event():
    text = (
        "SEBI had passed an Adjudication order dated January 31, 2012 against the Noticee, imposing penalty "
        "of Rs. 3,00,000/- under Section 15HA of the SEBI Act."
    )
    assert run("SEBI", "SEBI adjudication order", text) == []


def test_wtm_restraint_with_duration():
    text = (
        "Noticee Nos. 7 and 18 are hereby restrained from accessing the securities market and further "
        "prohibited from buying, selling or otherwise dealing in securities, for a period of four (4) years, "
        "from the date of this order."
    )
    (ev,) = run("SEBI", "SEBI whole-time member order", text)
    assert ev.arguments["action"] == "restraint"
    assert ev.arguments["duration"] == "four (4) years"
    assert ev.amount_inr is None
    assert ev.arguments["authority"] == "Whole-time Member"


def test_settlement_order_takes_the_settlement_amount():
    text = (
        "The IC recommended an amount of ₹9,37,500/- (Rupees Nine Lakhs Thirty-Seven Thousand Five "
        "Hundred only) as the settlement amount computed in terms of the Settlement Regulations."
    )
    (ev,) = run("SEBI", "SEBI settlement order", text)
    assert ev.arguments["action"] == "settlement" and ev.amount_inr == Decimal("937500")


NCLT = (
    "The Financial Creditor filed this application under Section 7 of the Insolvency and Bankruptcy "
    "Code, 2016. "
    "The Financial Creditor has proved the debt and default of the Corporate Debtor. "
    "Accordingly, the application is admitted and the Corporate Debtor is admitted into CIRP. "
    "A moratorium under Section 14 of the Code shall come into effect."
)


def test_nclt_admission_extracts_section_applicant_and_moratorium():
    (ev,) = run("NCLT", "NCLT admission order", NCLT)
    assert ev.type is EventType.NCLT_ADMISSION
    assert ev.arguments == {
        "section": "Section 7",
        "applicant_type": "financial creditor",
        "moratorium": "true",
    }
    assert "admitted into CIRP" in ev.trigger.slice(NCLT)
    assert ev.schema_valid


def test_no_operative_sentence_means_no_event():
    assert run("NCLT", "NCLT admission order", "The petition was heard and the matter adjourned.") == []
    assert run("SEBI", "SEBI adjudication order", "The proceedings are disposed of without penalty.") == []
    assert run("BSE", None, "Anything at all.") == []


YES = "Yes Bank Ltd"
PENALTY, SETTLEMENT, RESTRAINT = {"action": "penalty"}, {"action": "settlement"}, {"action": "restraint"}
SECTION_7 = {"section": "Section 7"}


@pytest.mark.parametrize(
    ("etype", "amount", "args", "expected"),
    [
        ("SEBI Penalty", Decimal(2500000), PENALTY, "SEBI penalty of ₹25 lakh on {}"),
        ("SEBI Penalty", Decimal(937500), SETTLEMENT, "SEBI settlement of ₹9.375 lakh with {}"),
        ("SEBI Penalty", None, RESTRAINT, "SEBI restrains {} from the securities market"),
        ("SEBI Penalty", None, {}, "SEBI enforcement order concerning {}"),
        ("NCLT Admission", None, SECTION_7, "NCLT admits {} into insolvency resolution (Section 7)"),
        ("Stock Split", None, {}, "Stock Split: {}"),
    ],
)
def test_headlines_use_only_extracted_facts(etype, amount, args, expected):
    assert headline(etype, YES, amount, args) == expected.format(YES)


def test_headline_for_an_unresolved_entity():
    assert (
        headline("NCLT Admission", None, None, {})
        == "NCLT admits an unresolved party into insolvency resolution"
    )


def test_following_penalty_reads_the_amount_from_the_lines_after_it():
    text = (
        "34. In exercise of the powers conferred upon me under section 15-I of the SEBI Act, I hereby impose "
        "following penalty under section 15HA of the SEBI Act, 1992 on the Noticee:\n\n"
        "Noticee Penalty Provision Rs. 5,00,000/- 15HA\n\n"
        "35. The penalty shall be paid within 45 days."
    )
    (ev,) = run("SEBI", "SEBI adjudication order", text)
    assert ev.arguments["action"] == "penalty"
    assert ev.amount_inr == Decimal(500000)
    assert ev.trigger.slice(text).endswith("on the Noticee:")


def test_following_penalty_with_a_table_of_several_noticees_leaves_the_amount_unset():
    text = (
        "I hereby impose the following penalty on the Noticees:\n\n"
        "Noticee 1 Rs. 5,00,000/-\n\nNoticee 2 Rs. 3,00,000/-"
    )
    (ev,) = run("SEBI", "SEBI adjudication order", text)
    assert ev.amount_inr is None
    assert ev.arguments["amounts_stated"] == "500000, 300000"


def test_no_penalty_orders_produce_no_event():
    text = "Consequently, no penalty is imposed on the Noticee, who is deceased, and the proceedings abate."
    assert run("SEBI", "SEBI adjudication order", text) == []
