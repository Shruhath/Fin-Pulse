"""One-line wording for an event, built only from what was extracted."""

from __future__ import annotations

from decimal import Decimal

from finpulse.preprocess.normalize import format_inr

from .taxonomy import EventType


def headline(
    event_type: str, entity: str | None, amount_inr: Decimal | None, arguments: dict[str, str]
) -> str:
    who = entity or "an unresolved party"
    kind = EventType(event_type)
    if kind is EventType.SEBI_PENALTY:
        action = arguments.get("action")
        if action == "penalty" and amount_inr is not None:
            return f"SEBI penalty of {format_inr(amount_inr)} on {who}"
        if action == "settlement" and amount_inr is not None:
            return f"SEBI settlement of {format_inr(amount_inr)} with {who}"
        if action == "restraint":
            return f"SEBI restrains {who} from the securities market"
        return f"SEBI enforcement order concerning {who}"
    if kind is EventType.NCLT_ADMISSION:
        section = arguments.get("section")
        suffix = f" ({section})" if section else ""
        return f"NCLT admits {who} into insolvency resolution{suffix}"
    return f"{kind.value}: {who}"
