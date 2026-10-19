"""The 16-type event taxonomy: EDT's 11 corporate types plus five India-specific ones.

Each type has a Pydantic model for its arguments. Every field is optional: an event is kept
when its type and trigger are found even if some arguments are not stated in the text, and
an absent argument is stored as absent, never guessed. The same models are the JSON schema
handed to the LLM extractor, and rule-based events are validated against them too.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal, get_args, get_origin

from pydantic import BaseModel, ConfigDict, Field


class EventType(StrEnum):
    ACQUISITION = "Acquisition"
    CLINICAL_TRIAL = "Clinical Trial"
    GUIDANCE_CHANGE = "Guidance Change"
    NEW_CONTRACT = "New Contract"
    STOCK_REPURCHASE = "Stock Repurchase"
    STOCK_SPLIT = "Stock Split"
    REVERSE_SPLIT = "Reverse Split"
    REGULAR_DIVIDEND = "Regular Dividend"
    SPECIAL_DIVIDEND = "Special Dividend"
    DIVIDEND_CUT = "Dividend Cut"
    DIVIDEND_INCREASE = "Dividend Increase"
    SEBI_PENALTY = "SEBI Penalty"
    RBI_ACTION = "RBI Action"
    NCLT_ADMISSION = "NCLT Admission"
    PLEDGE_INVOCATION = "Pledge Invocation"
    AUDITOR_RESIGNATION = "Auditor Resignation"


EVENT_GROUP: dict[EventType, str] = {
    EventType.ACQUISITION: "Corporate action",
    EventType.CLINICAL_TRIAL: "Corporate action",
    EventType.GUIDANCE_CHANGE: "Corporate action",
    EventType.NEW_CONTRACT: "Corporate action",
    EventType.STOCK_REPURCHASE: "Corporate action",
    EventType.STOCK_SPLIT: "Corporate action",
    EventType.REVERSE_SPLIT: "Corporate action",
    EventType.REGULAR_DIVIDEND: "Dividend",
    EventType.SPECIAL_DIVIDEND: "Dividend",
    EventType.DIVIDEND_CUT: "Dividend",
    EventType.DIVIDEND_INCREASE: "Dividend",
    EventType.SEBI_PENALTY: "Regulatory",
    EventType.RBI_ACTION: "Regulatory",
    EventType.NCLT_ADMISSION: "Insolvency",
    EventType.PLEDGE_INVOCATION: "Governance",
    EventType.AUDITOR_RESIGNATION: "Governance",
}

DEFINITIONS: dict[EventType, str] = {
    EventType.ACQUISITION: "A company agrees to buy, or completes buying, another company or a stake in it.",
    EventType.CLINICAL_TRIAL: "A clinical trial of a drug starts, reports results, or is stopped.",
    EventType.GUIDANCE_CHANGE: "A company raises, cuts or withdraws its published forecast or outlook.",
    EventType.NEW_CONTRACT: "A company wins or signs a new commercial contract or order.",
    EventType.STOCK_REPURCHASE: "A company announces or completes a buyback of its own shares.",
    EventType.STOCK_SPLIT: "A company splits its shares into more shares of lower face value.",
    EventType.REVERSE_SPLIT: "A company consolidates shares into fewer shares of higher face value.",
    EventType.REGULAR_DIVIDEND: "A company declares its ordinary interim or final dividend.",
    EventType.SPECIAL_DIVIDEND: "A company declares a one-off dividend outside its regular pattern.",
    EventType.DIVIDEND_CUT: "A company lowers its dividend against the previous one.",
    EventType.DIVIDEND_INCREASE: "A company raises its dividend against the previous one.",
    EventType.SEBI_PENALTY: "SEBI imposes a penalty, restrains a party from the market, or settles a case.",
    EventType.RBI_ACTION: "The RBI penalises, restricts or cancels the licence of a bank or NBFC.",
    EventType.NCLT_ADMISSION: "The NCLT admits an insolvency resolution application against a company.",
    EventType.PLEDGE_INVOCATION: "A lender invokes pledged promoter shares of a listed company.",
    EventType.AUDITOR_RESIGNATION: "A company's statutory auditor resigns before the end of its term.",
}


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AcquisitionArgs(_Args):
    type: Literal["Acquisition"] = "Acquisition"
    acquirer: str | None = None
    target: str | None = None
    amount_inr: Decimal | None = None
    stake_percent: Decimal | None = None


class ClinicalTrialArgs(_Args):
    type: Literal["Clinical Trial"] = "Clinical Trial"
    drug: str | None = None
    phase: str | None = None
    outcome: str | None = None


class GuidanceChangeArgs(_Args):
    type: Literal["Guidance Change"] = "Guidance Change"
    metric: str | None = None
    direction: Literal["raise", "cut", "withdraw", "maintain"] | None = None
    period: str | None = None


class NewContractArgs(_Args):
    type: Literal["New Contract"] = "New Contract"
    counterparty: str | None = None
    value_inr: Decimal | None = None
    scope: str | None = None


class StockRepurchaseArgs(_Args):
    type: Literal["Stock Repurchase"] = "Stock Repurchase"
    amount_inr: Decimal | None = None
    price_per_share_inr: Decimal | None = None
    mode: str | None = None


class StockSplitArgs(_Args):
    type: Literal["Stock Split"] = "Stock Split"
    ratio: str | None = None
    record_date: date | None = None


class ReverseSplitArgs(_Args):
    type: Literal["Reverse Split"] = "Reverse Split"
    ratio: str | None = None
    record_date: date | None = None


class DividendArgs(_Args):
    per_share_inr: Decimal | None = None
    previous_per_share_inr: Decimal | None = None
    record_date: date | None = None


class RegularDividendArgs(DividendArgs):
    type: Literal["Regular Dividend"] = "Regular Dividend"


class SpecialDividendArgs(DividendArgs):
    type: Literal["Special Dividend"] = "Special Dividend"


class DividendCutArgs(DividendArgs):
    type: Literal["Dividend Cut"] = "Dividend Cut"


class DividendIncreaseArgs(DividendArgs):
    type: Literal["Dividend Increase"] = "Dividend Increase"


class SEBIPenaltyArgs(_Args):
    type: Literal["SEBI Penalty"] = "SEBI Penalty"
    action: (
        Literal["penalty", "restraint", "settlement", "registration cancelled", "disgorgement", "warning"]
        | None
    ) = None
    amount_inr: Decimal | None = None
    provisions: list[str] = Field(default_factory=list)
    duration: str | None = None
    authority: str | None = None


class RBIActionArgs(_Args):
    type: Literal["RBI Action"] = "RBI Action"
    action: str | None = None
    amount_inr: Decimal | None = None
    provisions: list[str] = Field(default_factory=list)


class NCLTAdmissionArgs(_Args):
    type: Literal["NCLT Admission"] = "NCLT Admission"
    section: str | None = None
    applicant_type: Literal["financial creditor", "operational creditor", "corporate applicant"] | None = None
    moratorium: bool | None = None


class PledgeInvocationArgs(_Args):
    type: Literal["Pledge Invocation"] = "Pledge Invocation"
    promoter: str | None = None
    shares: int | None = None
    lender: str | None = None


class AuditorResignationArgs(_Args):
    type: Literal["Auditor Resignation"] = "Auditor Resignation"
    auditor: str | None = None
    reason: str | None = None
    effective_date: date | None = None


ARGUMENT_MODELS: dict[EventType, type[_Args]] = {
    EventType.ACQUISITION: AcquisitionArgs,
    EventType.CLINICAL_TRIAL: ClinicalTrialArgs,
    EventType.GUIDANCE_CHANGE: GuidanceChangeArgs,
    EventType.NEW_CONTRACT: NewContractArgs,
    EventType.STOCK_REPURCHASE: StockRepurchaseArgs,
    EventType.STOCK_SPLIT: StockSplitArgs,
    EventType.REVERSE_SPLIT: ReverseSplitArgs,
    EventType.REGULAR_DIVIDEND: RegularDividendArgs,
    EventType.SPECIAL_DIVIDEND: SpecialDividendArgs,
    EventType.DIVIDEND_CUT: DividendCutArgs,
    EventType.DIVIDEND_INCREASE: DividendIncreaseArgs,
    EventType.SEBI_PENALTY: SEBIPenaltyArgs,
    EventType.RBI_ACTION: RBIActionArgs,
    EventType.NCLT_ADMISSION: NCLTAdmissionArgs,
    EventType.PLEDGE_INVOCATION: PledgeInvocationArgs,
    EventType.AUDITOR_RESIGNATION: AuditorResignationArgs,
}


def argument_choices(event_type: EventType, key: str) -> list[str] | None:
    """The allowed values of an argument typed as a Literal, or None when it is free text."""
    for arg in get_args(ARGUMENT_MODELS[event_type].model_fields[key].annotation):
        if get_origin(arg) is Literal:
            return [str(v) for v in get_args(arg)]
    return None


def argument_fields(event_type: EventType) -> list[str]:
    """The argument names the model for `event_type` accepts (without the discriminator)."""
    return [name for name in ARGUMENT_MODELS[event_type].model_fields if name != "type"]


EventArgs = Annotated[
    AcquisitionArgs
    | ClinicalTrialArgs
    | GuidanceChangeArgs
    | NewContractArgs
    | StockRepurchaseArgs
    | StockSplitArgs
    | ReverseSplitArgs
    | RegularDividendArgs
    | SpecialDividendArgs
    | DividendCutArgs
    | DividendIncreaseArgs
    | SEBIPenaltyArgs
    | RBIActionArgs
    | NCLTAdmissionArgs
    | PledgeInvocationArgs
    | AuditorResignationArgs,
    Field(discriminator="type"),
]


class EventModel(BaseModel):
    """What the LLM extractor returns per event: the discriminated arguments plus its trigger sentence."""

    trigger_sentence_id: int
    args: EventArgs


def validate_arguments(event_type: EventType, arguments: dict[str, object]) -> bool:
    """True when `arguments` fits the model of `event_type`."""
    try:
        EventModel.model_validate({"trigger_sentence_id": 0, "args": {"type": event_type.value, **arguments}})
    except ValueError:
        return False
    return True
