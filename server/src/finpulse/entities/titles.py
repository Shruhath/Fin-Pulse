"""The parties an order is about, read from its title.

SEBI and IBBI titles name who an order concerns: "Adjudication Order in the matter of Selene
Estate Limited", "In the matter of Urvashi Material Trading Company Pvt. Ltd. [CP No. ...]",
"Adjudication order in respect of Galaxy Broking Ltd. in the matter of Monalisa Infotech Ltd".
The last form names two parties: the noticee and the company the matter concerns.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_I = re.IGNORECASE
_LEAD_IN = re.compile(
    r"\b(?:in\s+the\s+matter\s+of|in\s+respect(?:\s+of)?|in\s+the\s+case\s+of|in\s+re|against|regarding|"
    r"with\s+respect\s+to|consent\s+order\s+for|order\s+for)\s+|\border\s*[-–:]\s*",
    _I,
)
_SECOND_PARTY = re.compile(
    r"(?:\s+|(?<=\.))(?:in\s+(?:the\s+)?matter\s+of|in\s+the\s+scrip\s+of|in\s+re)\s+", _I
)  # also "Ltd.in the matter of", where the space is missing
_REPEATED_LEAD = re.compile(r"^(?:in\s+(?:the\s+)?matter\s+of\s+)+", _I)
_PERSON_IN_COMPANY = re.compile(r"^((?i:shri|smt\.?|mr\.?|mrs\.?|ms\.?|late|sri)\s+.+?)\s+in\s+([A-Z].+)$")
_LIST_MARKER = re.compile(r"^\(?(?:[ivx]{1,4}|[a-z]|\d{1,2})\)\s*", _I)
_FILLER = re.compile(
    r"^(?:the\s+)?(?:inspection\s+of|investigation\s+(?:in|into)|scrip\s+of|ipo\s+of|(?:the\s+)?(?:past|former)\s+"
    r"directors?\s+of|(?:the\s+)?(?:directors?|promoters?|proprietor)\s+of|shares\s+of)\s+",
    _I,
)
_HONORIFIC = re.compile(r"^(?:(?:m/s\.?|messrs\.?|shri|sri|smt\.?|mr\.?|mrs\.?|ms\.?|late|dr\.?)\s+)+", _I)
_CASE_NUMBER = re.compile(
    r"\s+(?:company\s+petition|c\.?\s?p\.?\s*(?:\(|no|-)|rcp|ib\s*[-(]|i\.?a\.?\s*(?:no|\()|c\.?a\.?\s*\().*$"
    r"|\s*\[.*$"
    r"|\s*\((?=[^)]*(?:\d|\bIB\b|\bCP\b|\bND\b|\bMB\b)).*$",
    _I,
)
_TAIL = re.compile(
    r"\s+(?:viz\.?|and\s+its|&\s+its|and\s+other|and\s+ors|&\s+ors|vs\.?|v\.)\s.*$|\s+(?:and|&)\s+ors\.?$|;.*$"
    r"|,?\s*\((?:now|formerly|erstwhile)\b.*$|,\s*(?:director|partner|proprietor|promoter)\b.*$"
    r"|\s+[-–]\s+(?:research|investment|registered|merchant|portfolio|stock)\b.*$",
    _I,
)
_NOT_A_PARTY = (
    "certain", "various", "the following", "entities", "noticees", "promoters", "persons",
    "dealing", "trading", "illiquid", "alleged", "non-", "failure", "violation", "front",
    "the scrip", "scrip", "self", "suspected", "insider",
)  # fmt: skip
_MULTI = re.compile(r",\s*(?:and\s+)?|\s+and\s+(?=(?:shri|smt|sri|mr|mrs|ms|m/s|late)\b)", _I)
_ROLE_WORD = re.compile(
    r"^(?:the\s+)?(?:director|directors|partner|partners|proprietor|promoter|promoters|ceo|cfo|chairman|"
    r"managing\s+director|company\s+secretary|compliance\s+officer|and\s+others?|others?)\b",
    _I,
)
_PERSON_MARK = re.compile(r"^(?:shri|sri|smt\.?|mr\.?|mrs\.?|ms\.?|late|dr\.?)\s", _I)
_COMPANY_WORD = re.compile(
    r"\b(?:limited|ltd|pvt|private|llp|bank|industries|company|co|corporation|corp|finance|securities|"
    r"infra\w*|power|energy|steel|textiles?|pharma\w*|services|enterprises|holdings|trading|capital|"
    r"developers|projects|foods|motors|realty|estate|investments?|exports?|agro|suppliers|solutions|"
    r"traders|academy|research|biotech|jewellers|properties|pictures|broking|beverages|prints)\b",
    _I,
)


_AND = re.compile(r"\s+and\s+", _I)

_MAX_PARTIES = 6
_MAX_NAME = 120


@dataclass(frozen=True, slots=True)
class TitleSubject:
    name: str
    kind: str  # company | person
    role: str  # subject (who the order is against) | matter (the company the matter concerns)


def _party(raw: str, role: str) -> TitleSubject | None:
    text = raw.strip()
    if text.lower().startswith(_NOT_A_PARTY):
        return None
    text = _LIST_MARKER.sub("", text)
    text = _FILLER.sub("", text)
    text = _CASE_NUMBER.sub("", text)
    text = _TAIL.sub("", text).strip(" .,-–—")
    honorific = bool(_PERSON_MARK.match(text))
    name = _HONORIFIC.sub("", text).strip(" .,-–—")
    if len(name) < 3 or name.lower().startswith(_NOT_A_PARTY):
        return None
    company_like = bool(_COMPANY_WORD.search(name))
    if role == "matter" and not company_like:
        return None  # "the matter of <something>" is only a party when it is a company
    person = (honorific and not company_like) or (not company_like and len(name.split()) <= 4)
    return TitleSubject(name, "person" if person else "company", role)


_RBI_PATTERNS = (
    re.compile(r"(?:monetary\s+)?penalt(?:y|ies)\s+(?:on|against|in\s+respect\s+of)\s+(?P<who>.+)$", _I),
    re.compile(r"(?:cancellation|cancels?|cancelled)\s+(?:of\s+)?(?:the\s+)?(?:certificate\s+of\s+registration|licen[cs]e)"
               r"\s+(?:of|issued\s+to|granted\s+to)\s+(?P<who>.+)$", _I),
    re.compile(r"^(?:directions|restrictions|order)\b.*?\s[–—-]\s+(?P<who>.+)$", _I),
)  # fmt: skip


def _rbi_subjects(text: str) -> list[TitleSubject]:
    for pattern in _RBI_PATTERNS:
        if m := pattern.search(text):
            who = re.split(r"\s+(?:for|under|vide|due\s+to)\s", m.group("who"), maxsplit=1)[0]
            who = re.sub(r"^the\s+", "", who, flags=_I)
            who = re.sub(
                r"(?i)((?:ltd|limited|bank|society)\.?),\s*[A-Z][A-Za-z .-]+$", r"\1", who
            )  # ", Ulhasnagar"
            party = _party(who, "subject")
            if party:
                return [TitleSubject(party.name, "company", "subject")]
    return []


def _split_people(chunk: str) -> list[str]:
    """Two people joined by "and" are two parties; "Kamlesh Jain and Co" is one firm."""
    parts = _AND.split(chunk)
    if len(parts) > 1 and not _COMPANY_WORD.search(chunk) and all(2 <= len(p.split()) <= 4 for p in parts):
        return parts
    return [chunk]


def title_subjects(title: str, source: str | None = None) -> list[TitleSubject]:
    """Every party the title names, the one the order is against first."""
    text = " ".join(title.split())
    if source == "RBI":
        return _rbi_subjects(text)
    lead = _LEAD_IN.search(text)
    if lead is None:
        return []
    rest = text[lead.end() :]
    rest = re.sub(r"^(?:in\s+the\s+matter\s+of\s+)+", "", rest, flags=_I)
    pieces = _SECOND_PARTY.split(rest)
    if len(pieces) == 1 and (m := _PERSON_IN_COMPANY.match(rest)):
        pieces = [m.group(1), m.group(2)]
    out: list[TitleSubject] = []
    for i, piece in enumerate(pieces[:2]):
        piece = _REPEATED_LEAD.sub("", piece)  # "in the matter of in the matter of X"
        role = "subject" if i == 0 else "matter"
        for chunk in _MULTI.split(piece)[:_MAX_PARTIES]:
            if not chunk or chunk.startswith("(") or _ROLE_WORD.match(chunk.strip()):
                continue
            for part in _split_people(chunk):
                party = _party(part, role)
                if party and len(party.name) <= _MAX_NAME:
                    out.append(party)
    return out


def title_subject(title: str) -> TitleSubject | None:
    found = title_subjects(title)
    return found[0] if found else None
