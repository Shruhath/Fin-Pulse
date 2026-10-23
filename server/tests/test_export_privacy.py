from finpulse.export.privacy import INDIVIDUAL, WITHHELD, Redactor, looks_like_individual, person_names

NAMES = ["Atul Shah", "Atul Kumar Shah", "Kanchan Agarwal", "Stock Broker", "22 entities", "to Ace Light"]


def test_contact_details_and_account_numbers_are_removed():
    r = Redactor()
    assert r.text("Write to cpjain@cacpjain.com or jain_cp@yahoo.com.") == "Write to [email] or [email]."
    assert r.text("Call +91 98765 43210 or 9876543210.") == "Call [phone] or [phone]."
    assert r.text("account no. 2XXX999XXX99 was frozen") == "account no. [account] was frozen"
    assert r.text("PAN ABCDE1234F paid") == "PAN XXXXXXXXXX paid"


def test_a_name_after_an_honorific_goes_and_the_role_stays():
    r = Redactor()
    assert (
        r.text("Mr. Ravindra Doshi, Managing Director of Kore, signed.")
        == f"{INDIVIDUAL}, Managing Director of Kore, signed."
    )
    assert r.text("Late Smt. Sharda Devi Bajaj held shares") == f"Late {INDIVIDUAL} held shares"
    assert r.text("Shri Jatin Shah was appointed") == f"{INDIVIDUAL} was appointed"


def test_known_individuals_are_replaced_whole_phrase_and_longest_first():
    r = Redactor(NAMES)
    assert r.text("Penalty on Atul Kumar Shah and atul shah.") == f"Penalty on {INDIVIDUAL} and {INDIVIDUAL}."
    assert r.text("Atul Shahi Traders") == "Atul Shahi Traders"


def test_entries_that_are_not_people_are_not_treated_as_names():
    assert person_names(NAMES) == ["Atul Kumar Shah", "Kanchan Agarwal", "Atul Shah"]
    r = Redactor(NAMES)
    text = "IIFL is a stock broker; 22 entities were named, including Ace Light."
    assert r.text(text) == text


def test_a_company_title_is_kept_and_an_individual_title_loses_the_name():
    r = Redactor(NAMES)
    assert (
        r.title("Adjudication order against Tulive Developers Ltd")
        == "Adjudication order against Tulive Developers Ltd"
    )
    assert (
        r.title("Consent order against Atul Shah in the matter of Continental Controls Ltd")
        == f"Consent order against {INDIVIDUAL} in the matter of Continental Controls Ltd"
    )
    assert (
        r.title("Adjudication Order in respect of Mr. Sunil Raheja in the matter of Synchronized Trades")
        == f"Adjudication Order in respect of {INDIVIDUAL} in the matter of Synchronized Trades"
    )
    assert (
        r.title("Adjudication Order in respect to Ace Light in the matter of Dealings in Stock Options")
        == f"Adjudication Order in respect to {WITHHELD} in the matter of Dealings in Stock Options"
    )
    assert (
        r.title("Adjudication Order in respect of 22 entities in the matter of Titan Company Limited")
        == "Adjudication Order in respect of 22 entities in the matter of Titan Company Limited"
    )
    assert r.title("In the matter of Yes Bank Limited") == "In the matter of Yes Bank Limited"


def test_strings_inside_event_arguments_are_cleaned_and_numbers_are_left_alone():
    r = Redactor(NAMES)
    arguments = {"noticee": "Kanchan Agarwal", "amount_inr": 500000, "parties": ["Mr. A B Rao", "Yes Bank"]}
    assert r.value(arguments) == {
        "noticee": INDIVIDUAL,
        "amount_inr": 500000,
        "parties": [INDIVIDUAL, "Yes Bank"],
    }
    assert r.value(None) is None


def test_titles_from_the_corpus_that_were_over_or_under_cleaned_at_first():
    r = Redactor(NAMES)
    assert (
        r.title(
            "Adjudication order in respect of Shri Jatin Shah In the matter of Oasis Media Matrix Limited"
        )
        == f"Adjudication order in respect of {INDIVIDUAL} In the matter of Oasis Media Matrix Limited"
    )
    assert (
        r.title("Adjudication Order in respect of Mr. Balasaheb J kamble in the matter of M/s. Flawless Ltd.")
        == f"Adjudication Order in respect of {INDIVIDUAL} in the matter of M/s. Flawless Ltd."
    )
    assert r.title("Order in the matter of Ms Pailan Park Development Authority Limited") == (
        "Order in the matter of Ms Pailan Park Development Authority Limited"
    )
    assert r.title(
        "Settlement Order in respect of SPG Prints B.V. in the matter of Stovec Industries Limited"
    ) == ("Settlement Order in respect of SPG Prints B.V. in the matter of Stovec Industries Limited")
    assert (
        r.title(
            "Consent order against Praveen Daga (HUF) in the matter of Trading Activity of Praveen Daga HUF"
        )
        == f"Consent order against {INDIVIDUAL} in the matter of Trading Activity of {INDIVIDUAL}"
    )
    assert (
        r.title("Order against Sri Sunil Laxman Kale and Trendline Traders Academy")
        == f"Order against {INDIVIDUAL}"
    )


def test_a_sole_practitioner_is_named_by_role_but_a_firm_with_a_body_word_is_kept():
    r = Redactor()
    assert r.title(
        "Adjudication Order in the matter of Inspection of records of Manu Chhabra Investment Adviser"
    ) == (f"Adjudication Order in the matter of Inspection of records of {INDIVIDUAL} Investment Adviser")
    assert r.title("Adjudication Order in the matter of Shares Bazaar Pvt. Ltd. - Research Analyst") == (
        "Adjudication Order in the matter of Shares Bazaar Pvt. Ltd. - Research Analyst"
    )


def test_names_a_reviewer_supplies_are_removed_as_given_and_a_colonel_is_an_honorific():
    r = Redactor(NAMES, extra_names=["Jai Sebastian", "Shashi Kiran Shetty", "ab"])
    assert (
        r.text("Jai Sebastian is the Adjudicating Officer.") == f"{INDIVIDUAL} is the Adjudicating Officer."
    )
    assert (
        r.text("The Shashi Kiran Shetty Family Trust owns 51%.") == f"The {INDIVIDUAL} Family Trust owns 51%."
    )
    assert r.text("petition filed by Col. Gautam Mullick & Ors.") == f"petition filed by {INDIVIDUAL} & Ors."
    assert r.text("ab is too short to match") == "ab is too short to match"


def test_an_unlisted_entity_without_a_company_word_is_treated_as_an_individual():
    assert looks_like_individual("Himadri Acharya Bhaduri and Atul Sharma", listed=False)
    assert looks_like_individual("Kiran Ajit Chawla and Jagjit Singh Chawla - HUF", listed=False)
    assert looks_like_individual("records of Manu Chhabra Investment Adviser", listed=False)
    assert not looks_like_individual("Zelkova Builders Private Limited", listed=False)
    assert not looks_like_individual("SPG Prints B.V", listed=False)
    assert not looks_like_individual("Tata Motors", listed=True)
