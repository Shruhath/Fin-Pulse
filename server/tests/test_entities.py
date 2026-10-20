import pytest

from finpulse.core.offsets import check_against
from finpulse.entities.matcher import AliasMatcher
from finpulse.entities.names import normalise_name, slugify, tokenize
from finpulse.entities.resolver import Resolver
from finpulse.entities.titles import title_subjects


@pytest.mark.parametrize(
    ("raw", "norm"),
    [
        ("Yes Bank Limited", "yes bank"),
        ("YES BANK LTD.", "yes bank"),
        ("M/s. Sintex Industries Pvt. Ltd.", "sintex industries"),
        ("The Tata Power Company Limited", "tata power"),
        ("Larsen & Toubro Ltd", "larsen and toubro"),
        ("Larsen and Toubro", "larsen and toubro"),
        ("Limited", "limited"),
    ],
)
def test_names_normalise_to_one_form(raw, norm):
    assert normalise_name(raw) == norm


def test_slug():
    assert slugify("Larsen & Toubro Ltd.") == "larsen-and-toubro"


def test_tokenize_keeps_offsets():
    text = "Yes Bank's order"
    toks = tokenize(text)
    assert [text[t.start : t.end] for t in toks] == ["Yes", "Bank's", "order"]


def _matcher():
    m = AliasMatcher()
    m.add("Yes Bank Limited", 1)
    m.add("Yes Bank", 1)
    m.add("Tata Motors Ltd", 2)
    m.add("Tata", 9)
    m.add("TCS", 3)
    m.add("Page Industries Limited", 4)
    m.add("Page", 4)
    m.add("Larsen & Toubro", 5)
    return m


def test_matcher_finds_spans_that_slice_to_the_surface():
    text = "SEBI penalised Yes Bank Limited and Tata Motors Ltd. on Monday; TCS also replied."
    found = _matcher().find(text)
    assert [(f.surface, f.entity_ids) for f in found] == [
        ("Yes Bank Limited", (1,)),
        ("Tata Motors Ltd", (2,)),
        ("TCS", (3,)),
    ]
    assert all(check_against(text, f.span, f.surface) for f in found)


def test_matcher_takes_a_following_legal_suffix_into_the_span():
    (f,) = _matcher().find("An order against Yes Bank Limited was passed.")
    assert f.surface == "Yes Bank Limited"


def test_a_bare_ticker_followed_by_more_capitalised_words_is_part_of_a_longer_name():
    m = AliasMatcher()
    m.add("ACC", 1)

    def surfaces(text):
        return [x.surface for x in m.find(text)]

    assert surfaces("REL held shares in ACC Energy Storage Pvt. Ltd. until 2025.") == []
    assert surfaces("The order names ACC Limited and others.") == ["ACC Limited"]
    assert surfaces("The shares of ACC. The company replied.") == ["ACC"]
    assert surfaces("Shares of ACC rose on Monday.") == ["ACC"]


def test_matcher_prefers_the_longest_alias():
    (f,) = _matcher().find("Tata Motors Ltd announced results.")
    assert f.entity_ids == (2,)


def test_matcher_ignores_lowercase_and_generic_words():
    assert _matcher().find("the yes bank of the world, a page of the file, tcs is short") == []
    assert _matcher().find("On this page the Board met.") == []


def test_matcher_handles_ampersands():
    (f,) = _matcher().find("Larsen & Toubro won a contract.")
    assert f.surface == "Larsen & Toubro" and f.entity_ids == (5,)


def test_matcher_matches_all_capitals_headings():
    (f,) = _matcher().find("IN THE MATTER OF YES BANK LIMITED")
    assert f.surface == "YES BANK LIMITED"


def test_resolver_exact_fuzzy_ambiguous_and_unresolved():
    r = Resolver({"yes bank": {1}, "tata motors": {2}, "bank of baroda": {3}, "tata": {7, 8}})
    assert r.resolve("YES BANK LTD").entity_id == 1
    assert r.resolve("YES BANK LTD").method == "normalised"
    assert r.resolve("Tata Motor Ltd").method == "fuzzy"
    assert r.resolve("Tata Motor Ltd").entity_id == 2
    assert r.resolve("Tata").method == "ambiguous" and r.resolve("Tata").entity_id is None
    assert r.resolve("Unknown Holdings Pvt Ltd") == r.resolve("Unknown Holdings Pvt Ltd")
    assert r.resolve("Unknown Holdings Pvt Ltd").entity_id is None


def test_fuzzy_does_not_merge_a_name_with_an_extended_one():
    r = Resolver({"yes bank": {1}})
    assert r.resolve("Yes Bank of America").entity_id is None


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Adjudication Order in the matter of Selene Estate Limited",
         [("subject", "company", "Selene Estate Limited")]),
        ("Adjudication Order in the matter of inspection of IIFL Capital Services Limited",
         [("subject", "company", "IIFL Capital Services Limited")]),
        ("In the matter of Urvashi Material Trading Company Pvt. Ltd. [CP No. (IB)-69/9/JPR/2025]",
         [("subject", "company", "Urvashi Material Trading Company Pvt. Ltd")]),
        ("In the matter of K V Developers Private Limited IB-236(ND)-2020",
         [("subject", "company", "K V Developers Private Limited")]),
        ("In the matter of Sare Facility (Gurgaon) Services Private Limited Company Petition No. IB-12/2020",
         [("subject", "company", "Sare Facility (Gurgaon) Services Private Limited")]),
        ("Order against M/s. Kamlesh Jain & Co", [("subject", "company", "Kamlesh Jain & Co")]),
        ("Adjudication Order in respect of Late Smt. Sharda Devi Bhagat",
         [("subject", "person", "Sharda Devi Bhagat")]),
        ("Settlement Order in respect of Shri Rakesh Kumar", [("subject", "person", "Rakesh Kumar")]),
        ("Interim Order - Polaris Agro Industries Limited",
         [("subject", "company", "Polaris Agro Industries Limited")]),
        ("Adjudication order in respect of Galaxy Broking Ltd. in the matter of Monalisa Infotech Ltd",
         [("subject", "company", "Galaxy Broking Ltd"), ("matter", "company", "Monalisa Infotech Ltd")]),
        ("Consent Order in respect of Ms. Gillian Adolf Pinto in the matter of KRBL Limited",
         [("subject", "person", "Gillian Adolf Pinto"), ("matter", "company", "KRBL Limited")]),
        ("Consent order for Shri Ashok Bharadia in Mazda Fabrics and Processors Ltd",
         [("subject", "person", "Ashok Bharadia"),
          ("matter", "company", "Mazda Fabrics and Processors Ltd")]),
        ("Order in the matter of Orthia Properties Private Limited, Zelkova Builders Private Limited, and "
         "Shri Sameer Gehlaut",
         [("subject", "company", "Orthia Properties Private Limited"),
          ("subject", "company", "Zelkova Builders Private Limited"),
          ("subject", "person", "Sameer Gehlaut")]),
        ("Adjudication order in respect of Ram Chandra Singh, Director, M/s Delton Exim Private Limited",
         [("subject", "person", "Ram Chandra Singh"), ("subject", "company", "Delton Exim Private Limited")]),
        ("Order against the past director of Sunplant Forgings Limited viz. Shri Ameet Singh",
         [("subject", "company", "Sunplant Forgings Limited")]),
        ("Adjudication Order in respect of Mrs. Simran Sunil Raheja in the matter of "
         "Self/Synchronized Trades in 12 Scrips",
         [("subject", "person", "Simran Sunil Raheja")]),
        ("Order in respect of Bubna Stock Broking Services Ltd., (now known as Sunbright Stock Broking Ltd.)",
         [("subject", "company", "Bubna Stock Broking Services Ltd")]),
        ("Adjudication Order in the matter of suspected insider trading in the scrip of Wipro Ltd",
         [("matter", "company", "Wipro Ltd")]),
        ("Order in respect of Himadri Acharya Bhaduri and Atul Sharma in the matter of in the matter of "
         "M/s. Action Financial Services (India) Ltd.",
         [("subject", "person", "Himadri Acharya Bhaduri"), ("subject", "person", "Atul Sharma"),
          ("matter", "company", "Action Financial Services (India) Ltd")]),
        ("Order in respect of Prakash Nahata and Co", [("subject", "company", "Prakash Nahata and Co")]),
        ("Order in the matter of Dipchand Development Co. Ltd.in the matter of SCORES Authentication",
         [("subject", "company", "Dipchand Development Co. Ltd")]),
    ],
)  # fmt: skip
def test_title_subjects(title, expected):
    got = [(t.role, t.kind, t.name.rstrip(".")) for t in title_subjects(title)]
    assert got == [(r, k, n.rstrip(".")) for r, k, n in expected]


def test_titles_without_a_party():
    assert title_subjects("Corrigendum") == []
    assert title_subjects("Order in the matter of certain entities in the scrip of ABC") == []
    assert title_subjects("Adjudication Order in the matter of trading activities of Someone") == []
