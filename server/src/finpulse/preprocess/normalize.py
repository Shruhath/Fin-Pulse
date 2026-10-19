"""Deterministic extractors for Indian regulatory text.

Every function returns values together with the exact `[start, end)` span they came from, so
callers can store offsets without searching the text again. Nothing here uses a model.

Conventions
- Amounts need a currency marker (Rs., INR, ₹, Rupees). A bare "6.4 crore warrants" is a
  count, not money, and is left alone.
- Numeric dates are day-first, as in Indian filings. "03/12/2023" is 3 December 2023.
  A numeric date that is not valid day-first is rejected, never guessed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from finpulse.core.offsets import Span

# --------------------------------------------------------------------------- amounts

_UNITS: dict[str, Decimal] = {
    "lakh crore": Decimal("1e12"),
    "lac crore": Decimal("1e12"),
    "crore": Decimal("1e7"),
    "cr": Decimal("1e7"),
    "lakh": Decimal("1e5"),
    "lac": Decimal("1e5"),
    "thousand": Decimal("1e3"),
    "million": Decimal("1e6"),
    "mn": Decimal("1e6"),
    "mln": Decimal("1e6"),
    "billion": Decimal("1e9"),
    "bn": Decimal("1e9"),
    "trillion": Decimal("1e12"),
    "tn": Decimal("1e12"),
}

# Longest alternatives first so "lakh crore" wins over "lakh".
_UNIT_RE = r"(?:lakh\s+crores?|lac\s+crores?|crores?|crs?|lakhs?|lacs?|thousand|million|mln|mn|billion|bn|trillion|tn)"
_NUMBER_RE = r"(?:\d{1,3}(?:,\d{2,3})+|\d+)(?:\.\d+)?"
_CURRENCY_RE = r"(?:Rs\.?|INR|₹|Rupees)"

_AMOUNT = re.compile(
    rf"(?P<cur>{_CURRENCY_RE})\s*(?P<num>{_NUMBER_RE})(?:\s*(?P<unit>{_UNIT_RE})(?![A-Za-z]))?(?:\s*/-)?",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class Amount:
    span: Span
    surface: str
    inr: Decimal


def _unit_multiplier(raw: str | None) -> Decimal:
    if not raw:
        return Decimal(1)
    key = re.sub(r"\s+", " ", raw.lower())
    return _UNITS[key.removesuffix("s")]  # crores, lakhs, lacs, crs


def find_amounts(text: str) -> list[Amount]:
    """Rupee amounts as exact INR values: "Rs. 1.5 lakh crore" is 1.5e12."""
    out: list[Amount] = []
    for m in _AMOUNT.finditer(text):
        inr = Decimal(m["num"].replace(",", "")) * _unit_multiplier(m["unit"])
        out.append(Amount(Span(m.start(), m.end()), m.group(0), inr))
    return out


def format_inr(value: Decimal) -> str:
    """Human wording for an amount, in Indian units: 25000000 -> "₹2.5 crore"."""
    v = abs(value)
    for threshold, unit in (
        (Decimal("1e12"), "lakh crore"),
        (Decimal("1e7"), "crore"),
        (Decimal("1e5"), "lakh"),
    ):
        if v >= threshold:
            scaled = (value / threshold).normalize()
            return f"₹{scaled:f} {unit}"
    return f"₹{value.normalize():f}"


# --------------------------------------------------------------------------- dates

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}  # fmt: skip
_MONTH_RE = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|Sept?(?:ember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"

_DATE_NUMERIC = re.compile(r"(?<![\d/.\-])(\d{1,2})([/.\-])(\d{1,2})\2(\d{4})(?![\d/])")
_DATE_DMY = re.compile(
    rf"(?<!\d)(\d{{1,2}})(?:st|nd|rd|th)?[\s\-,]*(?:of\s+)?({_MONTH_RE})\b\.?[\s\-,]*(\d{{4}})(?!\d)",
    re.IGNORECASE,
)
_DATE_MDY = re.compile(
    rf"\b({_MONTH_RE})\b\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?\s*,?\s*(\d{{4}})(?!\d)", re.IGNORECASE
)


@dataclass(frozen=True, slots=True)
class DateMention:
    span: Span
    surface: str
    value: date


def _safe_date(y: int, m: int, d: int) -> date | None:
    try:
        return date(y, m, d)
    except ValueError:
        return None


def find_dates(text: str) -> list[DateMention]:
    """Dates written the way Indian filings write them, as ISO `date`s, in text order."""
    found: list[DateMention] = []

    def add(m: re.Match[str], value: date | None) -> None:
        if value is not None and 1900 <= value.year <= 2100:
            found.append(DateMention(Span(m.start(), m.end()), m.group(0), value))

    for m in _DATE_NUMERIC.finditer(text):
        add(m, _safe_date(int(m[4]), int(m[3]), int(m[1])))
    for m in _DATE_DMY.finditer(text):
        add(m, _safe_date(int(m[3]), _MONTHS[m[2][:3].lower()], int(m[1])))
    for m in _DATE_MDY.finditer(text):
        add(m, _safe_date(int(m[3]), _MONTHS[m[1][:3].lower()], int(m[2])))

    found.sort(key=lambda d: (d.span.start, -d.span.length))
    unique: list[DateMention] = []
    for d in found:  # a pattern can match inside another's span; keep the first, longest
        if not unique or d.span.start >= unique[-1].span.end:
            unique.append(d)
    return unique


# --------------------------------------------------------------------------- identifiers

CIN_RE = re.compile(r"\b[LU]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}\b")
ISIN_RE = re.compile(r"\bIN[A-Z0-9]{9}\d\b")
PAN_RE = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")
_SCRIP_CONTEXT = re.compile(
    r"(?:scrip\s*code|security\s*code|bse\s*(?:code|:|scrip))\s*[:\-]?\s*(?P<code>\d{6})\b", re.IGNORECASE
)


def isin_valid(isin: str) -> bool:
    """ISO 6166 check digit: expand letters to 10..35, then Luhn over the digit string."""
    if not re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}\d", isin):
        return False
    digits = "".join(str(int(c, 36)) for c in isin)
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch)
        if i % 2 == 1:
            n *= 2
            n -= 9 if n > 9 else 0
        total += n
    return total % 10 == 0


@dataclass(frozen=True, slots=True)
class Identifier:
    kind: str  # cin | isin | pan | bse_scrip
    span: Span
    value: str


def find_identifiers(text: str) -> list[Identifier]:
    out: list[Identifier] = []
    for m in CIN_RE.finditer(text):
        out.append(Identifier("cin", Span(m.start(), m.end()), m.group(0)))
    for m in ISIN_RE.finditer(text):
        if isin_valid(m.group(0)):
            out.append(Identifier("isin", Span(m.start(), m.end()), m.group(0)))
    for m in PAN_RE.finditer(text):
        out.append(Identifier("pan", Span(m.start(), m.end()), m.group(0)))
    for m in _SCRIP_CONTEXT.finditer(text):
        out.append(Identifier("bse_scrip", Span(m.start("code"), m.end("code")), m["code"]))
    return sorted(out, key=lambda i: i.span.start)


def mask_pan(text: str) -> str:
    """Replace every PAN with X of the same length, so spans stay valid after masking."""
    return PAN_RE.sub(lambda m: "X" * len(m.group(0)), text)


# --------------------------------------------------------------------------- statutes

_INSTRUMENT = (
    r"(?:the\s+)?(?:(?:[A-Z][A-Za-z&()\-]*|and|of|for)\s+){0,8}?(?:Act|Regulations|Regulation|Rules|Code|Order|Circular)"
    r"(?:\s*,?\s*(?:19|20)\d{2})?"
)
_PROVISION = r"(?i:Sections?|Sec\.|Regulations?|Reg\.|Rules?|Clauses?)\s+\d+[A-Z]{0,2}(?:\s*\(\s*\w+\s*\))*"
_STATUTE = re.compile(
    rf"(?P<prov>{_PROVISION}(?:\s*(?:,|and|read with|r/w)\s*\d+[A-Z]{{0,2}}(?:\s*\(\s*\w+\s*\))*)*)"
    rf"\s+(?:of|under)\s+(?P<inst>{_INSTRUMENT})"
)


@dataclass(frozen=True, slots=True)
class StatuteRef:
    span: Span
    surface: str
    provision: str
    instrument: str


def find_statutes(text: str) -> list[StatuteRef]:
    """ "Section 11B of the SEBI Act, 1992" -> provision "Section 11B", instrument "SEBI Act, 1992"."""
    out: list[StatuteRef] = []
    for m in _STATUTE.finditer(text):
        inst = re.sub(r"^the\s+", "", m["inst"].strip(), flags=re.IGNORECASE)
        out.append(
            StatuteRef(Span(m.start(), m.end()), m.group(0), re.sub(r"\s+", " ", m["prov"]).strip(), inst)
        )
    return out
