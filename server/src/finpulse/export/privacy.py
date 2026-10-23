"""Remove personal data from the text fields the DataPort package keeps by default.

The package carries no document text, but three fields still hold words taken from the orders: the
document title, the arguments of an event and the text of a summary claim. SEBI orders name
individuals, so these are passed through here before they are written. The rules err on the side of
removing too much: a withheld name costs a little detail, a published one cannot be taken back.

What is removed
- e-mail addresses, Indian mobile numbers, PANs and bank account numbers;
- a name that follows an honorific (Mr, Mrs, Ms, Shri, Sri, Smt, Dr, ...), a Hindu undivided family
  (the name before "HUF") and a sole practitioner (the name before "Investment Adviser");
- every name or alias of an entity of kind `person` (see `person_names` for the ones left out);
- in a title, the party named after "in respect of" or "against" when nothing in it marks a company.

Company, bank and firm names are not personal data and stay.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from finpulse.preprocess.normalize import mask_pan

INDIVIDUAL = "[individual]"
WITHHELD = "[party withheld]"

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE = re.compile(r"(?<![\w.])(?:\+?91[\s-]?|0)?[6-9]\d{4}[\s-]?\d{5}(?![\w])")
_ACCOUNT = re.compile(r"(?i)(\baccount\s*(?:no\.?|number|#)\s*:?\s*)[\w-]*\d[\w-]{4,}")
_NAME_WORD = r"(?!(?:In|Of|The|And|Viz|For|To|On|At|By|As|Is|Was|Has|Had|Who|With|Against)\b)[A-Z][\w'’-]*\.?"
_HONORIFIC = re.compile(
    rf"\b(?:Mr|Mrs|Ms|Miss|Shri|Sri|Sh|Smt|Kumari|Dr|Prof|Col|Capt|Justice)\.?\s+{_NAME_WORD}(?:\s+{_NAME_WORD}){{0,3}}"
)
_HUF = re.compile(r"\b(?:[A-Z][\w'’-]*\s+){1,3}\(?HUF\)?")
# A sole practitioner is named after the person ("Manu Chhabra Investment Adviser").
_PRACTITIONER = re.compile(r"\b(?:[A-Z][\w'’-]*\s+){2,3}(?=(?:Investment Advis[eo]r|Research Analyst)\b)")

# A word that marks a legal person or a body, so a name containing it is not an individual.
_BODY_WORDS = frozenset(
    """ltd limited pvt private llp llc inc plc bank company corporation corp co industries finance
    securities exchange fund trust enterprises holdings services entity entities india international
    group ventures capital broker brokers brokerage association society authority board council
    committee ministry department government bv gmbh sa ag nv pte pty ulc lp sarl spa""".split()
)
_WORD = re.compile(r"[A-Za-z][\w'’-]*")
_PARTY = re.compile(r"(?i)\b(?:in respect (?:of|to)|against)\s+(?P<party>.+?)(?=\s+in the matter of\b|\s*$)")


def _words(text: str) -> list[str]:
    return [w.lower() for w in _WORD.findall(text.replace(".", ""))]


def _names_a_body(text: str) -> bool:
    return any(w in _BODY_WORDS for w in _words(text))


def person_names(entity_names: Iterable[str]) -> list[str]:
    """Names and aliases of `person` entities that really look like a person's name.

    The entity table is built from order titles, so a few entries of kind `person` are not people
    ("22 entities", "Stock Broker", a company that was typed wrongly). A name is kept only when it has
    at least two words, each starting with a capital letter, and no word that marks a body. Longest
    first, so "Atul Kumar Shah" is replaced before "Atul Shah".
    """
    kept: dict[str, str] = {}
    for name in entity_names:
        name = " ".join(name.split())
        tokens = name.split(" ")
        if len(tokens) < 2 or _names_a_body(name):
            continue
        if not all(t[:1].isupper() for t in tokens):
            continue
        kept.setdefault(name.lower(), name)
    return sorted(kept.values(), key=lambda n: (-len(n), n.lower()))


class Redactor:
    """Applies the rules above. Build it once per export and call it for every field."""

    def __init__(self, entity_names: Iterable[str] = (), extra_names: Iterable[str] = ()) -> None:
        """`entity_names`: names of `person` entities, filtered by `person_names`.

        `extra_names`: names a reviewer found in the text that no rule can see (a resolution professional
        or a signatory is not an entity). They are used as given, with no filtering.
        """
        extra = {" ".join(n.split()) for n in extra_names if len(" ".join(n.split())) >= 4}
        names = sorted({*person_names(entity_names), *extra}, key=lambda n: (-len(n), n.lower()))
        self._names = (
            re.compile(r"(?<![\w])(?:" + "|".join(re.escape(n) for n in names) + r")(?![\w])", re.IGNORECASE)
            if names
            else None
        )

    def text(self, text: str | None) -> str | None:
        if not text:
            return text
        out = _EMAIL.sub("[email]", text)
        out = _PHONE.sub("[phone]", out)
        out = _ACCOUNT.sub(r"\1[account]", out)
        out = mask_pan(out)
        out = _HONORIFIC.sub(lambda m: m.group(0) if _names_a_body(m.group(0)) else INDIVIDUAL, out)
        out = _HUF.sub(INDIVIDUAL, out)
        out = _PRACTITIONER.sub(lambda m: m.group(0) if _names_a_body(m.group(0)) else INDIVIDUAL + " ", out)
        if self._names:
            out = self._names.sub(INDIVIDUAL, out)
        return out

    def title(self, title: str | None) -> str | None:
        if not title:
            return title
        out = self.text(title) or title
        party = _PARTY.search(out)
        if party:
            who = party.group("party").strip()
            if (who[:1].isupper() or who.startswith(INDIVIDUAL)) and not _names_a_body(who):
                label = INDIVIDUAL if INDIVIDUAL in who else WITHHELD
                out = out[: party.start("party")] + label + out[party.end("party") :]
        return out

    def value(self, value: Any) -> Any:
        """Redact every string inside a JSON-like value (event arguments)."""
        if isinstance(value, str):
            return self.text(value)
        if isinstance(value, list):
            return [self.value(v) for v in value]
        if isinstance(value, dict):
            return {k: self.value(v) for k, v in value.items()}
        return value
