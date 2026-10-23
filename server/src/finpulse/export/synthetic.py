"""FinPulse Synthetic Filings v1: a fictional benchmark with the structure of the real corpus.

Every company, amount, date and sentence here is invented. The filings are written from templates in the
register of SEBI orders, NCLT admission orders, RBI press releases and company announcements, and the labels
are known by construction, because the same template that writes a sentence says what it means: which
company it is about, how it reads for that company, which event it reports and which claims follow from it.
So the gold files are exact, not annotated after the fact.

Why it exists: the real orders cannot be redistributed without the publishers' permission, and they name
individuals. A synthetic set lets others run and test entity-level sentiment, event extraction and
claim verification against exact labels. It says nothing about real companies, and a model that does well
on it has shown only that it can read this style of text, not that it works on real filings.

The generator is deterministic: the same code writes the same files.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from finpulse.sentiment.data import LABELS

# Fixed by hand because there are only 13 filings: a hash split would leave a split empty.
SPLIT = {"sebi-3": "dev", "nclt-3": "dev", "sebi-4": "test", "nclt-4": "test"}

LICENSE = """FinPulse Synthetic Filings v1: Creative Commons Attribution 4.0 International (CC BY 4.0)
https://creativecommons.org/licenses/by/4.0/legalcode

All text and labels in this package were written for it. The companies, people, amounts and dates are
fictional, and any resemblance to a real company is coincidental. You may share and adapt it, including
commercially, if you give appropriate credit, link to the licence and say whether changes were made.
"""


@dataclass(slots=True)
class Sentence:
    text: str
    labels: dict[str, str] = field(default_factory=dict)  # company -> how this sentence reads for it


@dataclass(slots=True)
class Filing:
    key: str
    source: str  # SEBI | NCLT | RBI | BSE | NSE
    doc_type: str
    title: str
    published: date
    sentences: list[Sentence]
    events: list[dict[str, Any]]
    claims: list[dict[str, Any]]


def _d(day: date) -> str:
    return f"{day.strftime('%B')} {day.day}, {day.year}"


def _rs(amount: int) -> str:
    """Rupees with lakh grouping: 1250000 -> 12,50,000."""
    whole = str(amount)
    head, tail = whole[:-3], whole[-3:]
    groups: list[str] = []
    while head:
        groups.insert(0, head[-2:])
        head = head[:-2]
    return ",".join([*groups, tail])


def _sebi(
    i: int, company: str, business: str, what: str, days: int, reg: str, amount: int, when: date
) -> Filing:
    s = [
        Sentence("BEFORE THE ADJUDICATING OFFICER, SECURITIES AND EXCHANGE BOARD OF INDIA"),
        Sentence(f"In the matter of {company}.", {company: "neutral"}),
        Sentence(
            f"{company} (hereinafter the Noticee) is listed on "
            f"the stock exchanges and is engaged in {business}.",
            {company: "neutral"},
        ),
        Sentence(
            f"SEBI examined the disclosures made by {company} for "
            f"the quarter ended {_d(date(when.year - 1, 12, 31))}.",
            {company: "neutral"},
        ),
        Sentence(
            f"It was found that {company} delayed the disclosure of {what} by {days} days, in violation of "
            f"Regulation {reg} of the SEBI (Listing Obligations "
            "and Disclosure Requirements) Regulations, 2015.",
            {company: "negative"},
        ),
        Sentence(
            "A show cause notice was issued to the Noticee and a "
            f"hearing was held on {_d(date(when.year, when.month, 2))}."
        ),
        Sentence("The Noticee submitted that the delay was inadvertent and caused no loss to investors."),
        Sentence(
            "Having considered the submissions, the Adjudicating Officer "
            "holds that the Noticee has violated the said regulation."
        ),
        Sentence(
            f"A penalty of Rs. {_rs(amount)} is imposed on "
            f"{company} under Section 15A(b) of the SEBI Act, 1992.",
            {company: "negative"},
        ),
        Sentence("The Noticee shall pay the penalty within 45 days of receipt of this order."),
    ]
    return Filing(
        f"sebi-{i}",
        "SEBI",
        "SEBI adjudication order",
        f"Adjudication order in the matter of {company}",
        when,
        s,
        [
            {
                "type": "SEBI Penalty",
                "sentence": 8,
                "entity": company,
                "arguments": {
                    "action": "penalty",
                    "authority": "SEBI",
                    "amount_inr": amount,
                    "provisions": "Section 15A(b) of the SEBI Act, 1992",
                },
            }
        ],
        [
            {
                "text": f"SEBI imposed a penalty of Rs. {_rs(amount)} on {company}.",
                "verdict": "entailed",
                "evidence": [8],
            },
            {
                "text": f"{company} delayed the disclosure of {what} by {days} days.",
                "verdict": "entailed",
                "evidence": [4],
            },
            {
                "text": "The penalty has to be paid within 45 days of receipt of the order.",
                "verdict": "entailed",
                "evidence": [9],
            },
            {
                "text": f"SEBI held that {company} had not violated any regulation.",
                "verdict": "contradicted",
                "evidence": [7],
            },
            {
                "text": f"{company} was barred from accessing the securities market.",
                "verdict": "unverified",
                "evidence": [],
            },
        ],
    )


def _nclt(i: int, debtor: str, creditor: str, bench: str, loan: int, default: int, when: date) -> Filing:
    s = [
        Sentence(f"IN THE NATIONAL COMPANY LAW TRIBUNAL, {bench.upper()} BENCH"),
        Sentence(
            f"{creditor} (the Financial Creditor) versus {debtor} (the Corporate Debtor).",
            {creditor: "neutral", debtor: "neutral"},
        ),
        Sentence(
            "This petition under Section 7 of the Insolvency and Bankruptcy "
            f"Code, 2016 has been filed by {creditor} against {debtor}.",
            {creditor: "neutral", debtor: "negative"},
        ),
        Sentence(
            f"{creditor} sanctioned a term loan of Rs. {_rs(loan)} "
            f"to {debtor} on {_d(date(when.year - 3, 6, 14))}.",
            {creditor: "neutral", debtor: "neutral"},
        ),
        Sentence(
            f"{debtor} defaulted in repayment and the account was classified "
            f"as non-performing on {_d(date(when.year - 1, 3, 31))}.",
            {debtor: "negative"},
        ),
        Sentence(f"The amount in default is Rs. {_rs(default)} as on {_d(date(when.year - 1, 9, 30))}."),
        Sentence(
            "The Tribunal is satisfied that a default has occurred and that the application is complete."
        ),
        Sentence(
            "The petition is admitted and the Corporate Insolvency "
            f"Resolution Process is initiated against {debtor}.",
            {debtor: "negative"},
        ),
        Sentence("A moratorium under Section 14 of the Code is declared from the date of this order."),
        Sentence(
            f"The Tribunal appoints an Interim Resolution Professional to manage the affairs of {debtor}.",
            {debtor: "neutral"},
        ),
    ]
    return Filing(
        f"nclt-{i}",
        "NCLT",
        "NCLT admission order",
        f"In the matter of {debtor}",
        when,
        s,
        [
            {
                "type": "NCLT Admission",
                "sentence": 7,
                "entity": debtor,
                "arguments": {
                    "section": "Section 7",
                    "applicant_type": "financial creditor",
                    "moratorium": True,
                },
            }
        ],
        [
            {
                "text": "The Tribunal admitted the insolvency petition "
                f"filed by {creditor} against {debtor}.",
                "verdict": "entailed",
                "evidence": [7],
            },
            {"text": f"The amount in default is Rs. {_rs(default)}.", "verdict": "entailed", "evidence": [5]},
            {
                "text": f"{creditor} sanctioned a term loan of Rs. {_rs(loan)} to {debtor}.",
                "verdict": "entailed",
                "evidence": [3],
            },
            {
                "text": f"The Tribunal rejected the petition against {debtor}.",
                "verdict": "contradicted",
                "evidence": [7],
            },
            {
                "text": f"{debtor} has agreed a resolution plan with its lenders.",
                "verdict": "unverified",
                "evidence": [],
            },
        ],
    )


def _rbi(i: int, bank: str, amount: int, rule: str, when: date) -> Filing:
    s = [
        Sentence(f"RBI imposes monetary penalty on {bank}", {bank: "negative"}),
        Sentence(
            "The Reserve Bank of India has imposed a monetary penalty of Rs. "
            f"{_rs(amount)} on {bank} for non-compliance with directions on {rule}.",
            {bank: "negative"},
        ),
        Sentence(
            "The penalty has been imposed in exercise of the powers conferred "
            "under Section 47A(1)(c) of the Banking Regulation Act, 1949."
        ),
        Sentence(
            f"A statutory inspection of {bank} with reference to its financial position "
            f"as on March 31, {when.year - 1} was conducted by the Reserve Bank.",
            {bank: "neutral"},
        ),
        Sentence(
            f"A notice was issued to {bank} advising it to show cause why a penalty should not be imposed.",
            {bank: "neutral"},
        ),
        Sentence(
            "After considering the reply and the oral submissions, the "
            "Reserve Bank concluded that the charge was substantiated."
        ),
        Sentence(
            "This action is based on regulatory compliance and is not intended to pronounce upon the "
            "validity of any transaction or agreement entered into by the bank with its customers."
        ),
    ]
    return Filing(
        f"rbi-{i}",
        "RBI",
        "RBI press release",
        f"RBI imposes monetary penalty on {bank}",
        when,
        s,
        [
            {
                "type": "RBI Action",
                "sentence": 1,
                "entity": bank,
                "arguments": {
                    "action": "penalty",
                    "amount_inr": amount,
                    "provisions": "Section 47A(1)(c) of the Banking Regulation Act, 1949",
                },
            }
        ],
        [
            {
                "text": f"The Reserve Bank imposed a penalty of Rs. {_rs(amount)} on {bank}.",
                "verdict": "entailed",
                "evidence": [1],
            },
            {
                "text": f"The penalty relates to non-compliance with directions on {rule}.",
                "verdict": "entailed",
                "evidence": [1],
            },
            {
                "text": f"The Reserve Bank cancelled the licence of {bank}.",
                "verdict": "contradicted",
                "evidence": [6],
            },
            {
                "text": f"Depositors of {bank} may withdraw only a limited amount.",
                "verdict": "unverified",
                "evidence": [],
            },
        ],
    )


def _dividend(i: int, company: str, now: float, before: float, profit: int, rise: int, when: date) -> Filing:
    s = [
        Sentence(f"Outcome of the Board Meeting of {company}", {company: "neutral"}),
        Sentence(
            f"The Board of Directors of {company} met on {_d(when)} and approved the "
            f"audited financial results for the year ended March 31, {when.year}.",
            {company: "neutral"},
        ),
        Sentence(
            f"Profit after tax of {company} rose {rise} percent to Rs. {profit} crore from "
            f"Rs. {round(profit / (1 + rise / 100))} crore in the previous year.",
            {company: "positive"},
        ),
        Sentence(
            f"The Board of {company} recommended a final dividend of Rs. {now:.1f} per equity share "
            f"of face value Rs. 10 each, against Rs. {before:.1f} paid last year.",
            {company: "positive"},
        ),
        Sentence(
            "The dividend, if approved by the shareholders at the "
            "annual general meeting, will be paid within 30 days."
        ),
        Sentence("The Board meeting commenced at 11:00 a.m. and concluded at 2:30 p.m."),
    ]
    return Filing(
        f"announcement-div-{i}",
        "NSE",
        "Company announcement",
        f"{company}: outcome of board meeting",
        when,
        s,
        [
            {
                "type": "Dividend Increase",
                "sentence": 3,
                "entity": company,
                "arguments": {"per_share_inr": now, "previous_per_share_inr": before},
            }
        ],
        [
            {
                "text": f"{company} recommended a final dividend of Rs. {now:.1f} per share.",
                "verdict": "entailed",
                "evidence": [3],
            },
            {
                "text": f"Profit after tax of {company} rose {rise} percent.",
                "verdict": "entailed",
                "evidence": [2],
            },
            {
                "text": f"{company} cut its dividend compared with the previous year.",
                "verdict": "contradicted",
                "evidence": [3],
            },
            {"text": f"{company} announced a share buyback.", "verdict": "unverified", "evidence": []},
        ],
    )


def _acquisition(i: int, buyer: str, target: str, stake: int, amount: int, when: date) -> Filing:
    s = [
        Sentence(f"{buyer}: acquisition of {target}", {buyer: "positive", target: "neutral"}),
        Sentence(
            f"{buyer} has entered into a share purchase agreement to acquire "
            f"{stake} percent of the equity share capital of {target}.",
            {buyer: "positive", target: "neutral"},
        ),
        Sentence(f"The consideration is Rs. {_rs(amount)} payable in cash.", {}),
        Sentence(
            f"{target} is engaged in the manufacture of sensors and had "
            "a turnover of Rs. 84 crore in the last financial year.",
            {target: "neutral"},
        ),
        Sentence(
            "The acquisition is expected to be completed within "
            "three months, subject to customary conditions."
        ),
        Sentence(
            "The acquisition is not a related party transaction, and "
            f"no promoter of {buyer} has any interest in {target}.",
            {buyer: "neutral", target: "neutral"},
        ),
    ]
    return Filing(
        f"announcement-acq-{i}",
        "BSE",
        "Company announcement",
        f"{buyer}: acquisition of {target}",
        when,
        s,
        [
            {
                "type": "Acquisition",
                "sentence": 1,
                "entity": buyer,
                "arguments": {
                    "acquirer": buyer,
                    "target": target,
                    "amount_inr": amount,
                    "stake_percent": stake,
                },
            }
        ],
        [
            {
                "text": f"{buyer} agreed to acquire {stake} percent of {target}.",
                "verdict": "entailed",
                "evidence": [1],
            },
            {
                "text": f"The consideration is Rs. {_rs(amount)}, payable in cash.",
                "verdict": "entailed",
                "evidence": [2],
            },
            {
                "text": f"{buyer} agreed to sell {stake} percent of its own shares.",
                "verdict": "contradicted",
                "evidence": [1],
            },
            {
                "text": f"{target} reported a loss in the last financial year.",
                "verdict": "unverified",
                "evidence": [],
            },
        ],
    )


def _contract(i: int, company: str, goods: str, crore: int, months: int, share: int, when: date) -> Filing:
    s = [
        Sentence(f"{company}: receipt of order", {company: "positive"}),
        Sentence(
            f"{company} has received a purchase order worth Rs. {crore} crore from a public sector "
            f"undertaking for the supply of {goods}.",
            {company: "positive"},
        ),
        Sentence(f"The order is to be executed over {months} months from the date of receipt."),
        Sentence(
            f"The order is expected to add about {share} percent to the revenue of {company} "
            "in the current financial year.",
            {company: "positive"},
        ),
        Sentence("The company does not expect the order to have any material impact on its profit margins."),
        Sentence(
            "This disclosure is made under Regulation 30 of the SEBI (Listing Obligations and "
            "Disclosure Requirements) Regulations, 2015."
        ),
    ]
    return Filing(
        f"announcement-order-{i}",
        "BSE",
        "Company announcement",
        f"{company}: receipt of order",
        when,
        s,
        [
            {
                "type": "New Contract",
                "sentence": 1,
                "entity": company,
                "arguments": {
                    "counterparty": "a public sector undertaking",
                    "value_inr": crore * 10_000_000,
                    "scope": goods,
                },
            }
        ],
        [
            {
                "text": f"{company} received an order worth Rs. {crore} crore.",
                "verdict": "entailed",
                "evidence": [1],
            },
            {
                "text": f"The order is to be executed over {months} months.",
                "verdict": "entailed",
                "evidence": [2],
            },
            {
                "text": f"The order is expected to add about {share} percent to the revenue of {company}.",
                "verdict": "entailed",
                "evidence": [3],
            },
            {
                "text": f"The order has to be executed within {months // 3} months.",
                "verdict": "contradicted",
                "evidence": [2],
            },
            {
                "text": f"{company} won the order against three other bidders.",
                "verdict": "unverified",
                "evidence": [],
            },
        ],
    )


def filings() -> list[Filing]:
    out: list[Filing] = []
    sebi = [
        (
            "Zorvex Polymers Limited",
            "the manufacture of industrial polymers",
            "its quarterly financial results",
            12,
            "33",
            500000,
            date(2026, 3, 18),
        ),
        (
            "Kavora Electronics Limited",
            "the manufacture of consumer electronics",
            "a change in its statutory auditor",
            9,
            "30",
            300000,
            date(2026, 4, 22),
        ),
        (
            "Tamrix Auto Components Limited",
            "the manufacture of automotive components",
            "a related party transaction",
            21,
            "23",
            1000000,
            date(2026, 5, 9),
        ),
        (
            "Lunaris Pharma Limited",
            "the manufacture of generic medicines",
            "the outcome of a board meeting",
            6,
            "30",
            200000,
            date(2026, 6, 3),
        ),
    ]
    for i, args in enumerate(sebi, start=1):
        out.append(_sebi(i, *args))
    nclt = [
        (
            "Brevan Textiles Private Limited",
            "Fenwick Capital Finance Limited",
            "Chennai",
            45000000,
            61200000,
            date(2026, 2, 12),
        ),
        (
            "Quillon Steel Private Limited",
            "Harlow Bank Limited",
            "Mumbai",
            120000000,
            154300000,
            date(2026, 3, 27),
        ),
        (
            "Ostrava Foods Private Limited",
            "Meridia Housing Finance Limited",
            "Hyderabad",
            32000000,
            41800000,
            date(2026, 5, 15),
        ),
        (
            "Nexmore Logistics Private Limited",
            "Corvell Leasing Limited",
            "Ahmedabad",
            18500000,
            23900000,
            date(2026, 6, 30),
        ),
    ]
    for i, args in enumerate(nclt, start=1):
        out.append(_nclt(i, *args))
    rbi = [
        ("Vestria Urban Co-operative Bank Limited", 1000000, "know your customer norms", date(2026, 7, 8)),
        ("Palmora Small Finance Bank Limited", 2500000, "interest rate on advances", date(2026, 8, 19)),
    ]
    for i, args in enumerate(rbi, start=1):
        out.append(_rbi(i, *args))
    out.append(_dividend(1, "Zorvex Polymers Limited", 6.5, 5.0, 188, 24, date(2026, 5, 20)))
    out.append(
        _acquisition(
            1,
            "Kavora Electronics Limited",
            "Dunmere Sensors Private Limited",
            60,
            210000000,
            date(2026, 7, 14),
        )
    )
    out.append(_dividend(2, "Lunaris Pharma Limited", 3.0, 2.5, 96, 12, date(2026, 8, 5)))
    out.append(
        _contract(
            1, "Tamrix Auto Components Limited", "forged steel components", 142, 18, 9, date(2026, 6, 11)
        )
    )
    out.append(_contract(2, "Brindel Engineering Limited", "switchgear panels", 87, 12, 6, date(2026, 9, 2)))
    return out


def _latex(text: str) -> str:
    for a, b in (
        ("\\", "\\textbackslash{}"),
        ("&", "\\&"),
        ("%", "\\%"),
        ("$", "\\$"),
        ("#", "\\#"),
        ("_", "\\_"),
    ):
        text = text.replace(a, b)
    return text


def _tex(f: Filing) -> str:
    body = "\n\n".join(_latex(s.text) for s in f.sentences[1:])
    return (
        "\\documentclass[11pt]{article}\n\\usepackage[margin=1in]{geometry}\n\\begin{document}\n"
        f"\\begin{{center}}\\textbf{{{_latex(f.sentences[0].text)}}}\\end{{center}}\n\n"
        f"\\noindent\\textit{{{_latex(f.doc_type)}, {_d(f.published)}. "
        "Synthetic: every name and figure is fictional.}\n\n"
        f"{body}\n\\end{{document}}\n"
    )


def _hash(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()


def build_synthetic(out_dir: Path) -> dict[str, int]:
    """Write the package under `out_dir` and return its counts."""
    (out_dir / "documents").mkdir(parents=True, exist_ok=True)
    (out_dir / "splits").mkdir(exist_ok=True)
    docs, sents, mentions, entities = [], [], [], {}
    gold_sentiment: list[dict[str, Any]] = []
    gold_events: list[dict[str, Any]] = []
    gold_summaries: list[dict[str, Any]] = []
    for doc_id, f in enumerate(filings(), start=1):
        text = "\n".join(s.text for s in f.sentences)
        starts, at = [], 0
        for s in f.sentences:
            starts.append(at)
            at += len(s.text) + 1
        (out_dir / "documents" / f"{f.key}.txt").write_text(text + "\n", encoding="utf-8")
        (out_dir / "documents" / f"{f.key}.tex").write_text(_tex(f), encoding="utf-8")
        docs.append(
            {
                "doc_id": doc_id,
                "key": f.key,
                "source_kind": f.source,
                "doc_type": f.doc_type,
                "title": f.title,
                "published_at": f.published,
                "sha256": _hash(text),
                "n_words": len(text.split()),
                "synthetic": True,
                "text": text,
            }
        )
        for idx, s in enumerate(f.sentences):
            sents.append(
                {
                    "doc_id": doc_id,
                    "idx": idx,
                    "char_start": starts[idx],
                    "char_end": starts[idx] + len(s.text),
                    "text": s.text,
                }
            )
            for company, label in s.labels.items():
                assert label in LABELS
                entities.setdefault(
                    company,
                    {
                        "slug": _slug(company),
                        "canonical_name": company,
                        "kind": "bank" if "Bank" in company else "company",
                        "synthetic": True,
                    },
                )
                where = s.text.find(company)
                while where >= 0:
                    start = starts[idx] + where
                    mentions.append(
                        {
                            "doc_id": doc_id,
                            "char_start": start,
                            "char_end": start + len(company),
                            "entity": _slug(company),
                            "surface": company,
                        }
                    )
                    gold_sentiment.append(
                        {
                            "doc_id": doc_id,
                            "char_start": start,
                            "char_end": start + len(company),
                            "entity": _slug(company),
                            "surface": company,
                            "label": label,
                            "label_source": "authored",
                        }
                    )
                    where = s.text.find(company, where + len(company))
        for e in f.events:
            i = e["sentence"]
            gold_events.append(
                {
                    "doc_id": doc_id,
                    "type": e["type"],
                    "trigger": [starts[i], starts[i] + len(f.sentences[i].text)],
                    "entity": _slug(e["entity"]),
                    "arguments": e["arguments"],
                    "label_source": "authored",
                }
            )
        gold_summaries.append(
            {
                "doc_id": doc_id,
                "label_source": "authored",
                "claims": [
                    {
                        "text": c["text"],
                        "verdict": c["verdict"],
                        "evidence_sentence_idx": c["evidence"],
                        "evidence_char_spans": [
                            [starts[k], starts[k] + len(f.sentences[k].text)] for k in c["evidence"]
                        ],
                    }
                    for c in f.claims
                ],
            }
        )

    def table(name: str, rows: list[dict[str, Any]], schema: dict[str, pa.DataType]) -> int:
        pq.write_table(
            pa.Table.from_pylist(rows, schema=pa.schema(list(schema.items()))),
            out_dir / name,
            compression="zstd",
        )
        return len(rows)

    counts = {
        "documents": table(
            "documents.parquet",
            docs,
            {
                "doc_id": pa.int64(),
                "key": pa.string(),
                "source_kind": pa.string(),
                "doc_type": pa.string(),
                "title": pa.string(),
                "published_at": pa.date32(),
                "sha256": pa.string(),
                "n_words": pa.int32(),
                "synthetic": pa.bool_(),
                "text": pa.string(),
            },
        ),
        "sentences": table(
            "sentences.parquet",
            sents,
            {
                "doc_id": pa.int64(),
                "idx": pa.int32(),
                "char_start": pa.int32(),
                "char_end": pa.int32(),
                "text": pa.string(),
            },
        ),
        "mentions": table(
            "mentions.parquet",
            mentions,
            {
                "doc_id": pa.int64(),
                "char_start": pa.int32(),
                "char_end": pa.int32(),
                "entity": pa.string(),
                "surface": pa.string(),
            },
        ),
        "entities": table(
            "entities.parquet",
            list(entities.values()),
            {
                "slug": pa.string(),
                "canonical_name": pa.string(),
                "kind": pa.string(),
                "synthetic": pa.bool_(),
            },
        ),
    }
    for name, rows in (
        ("sentiment_gold.jsonl", gold_sentiment),
        ("events_gold.jsonl", gold_events),
        ("summaries_gold.jsonl", gold_summaries),
    ):
        (out_dir / name).write_text(
            "".join(json.dumps(r, ensure_ascii=False, default=str) + "\n" for r in rows), encoding="utf-8"
        )
        counts[name.removesuffix(".jsonl")] = len(rows)
    counts["claims"] = sum(len(g["claims"]) for g in gold_summaries)
    split: dict[str, list[int]] = {"train": [], "dev": [], "test": []}
    for d in docs:
        split[SPLIT.get(d["key"], "train")].append(d["doc_id"])
    for name, ids in split.items():
        (out_dir / "splits" / f"{name}.txt").write_text("".join(f"{i}\n" for i in ids))
        counts[f"split_{name}"] = len(ids)
    (out_dir / "README.md").write_text(
        (Path(__file__).with_name("synthetic_readme.md")).read_text(encoding="utf-8"), encoding="utf-8"
    )
    (out_dir / "LICENSE.txt").write_text(LICENSE, encoding="utf-8")
    files = sorted(p for p in out_dir.rglob("*") if p.is_file() and p.name != "MANIFEST.json")
    (out_dir / "MANIFEST.json").write_text(
        json.dumps(
            {
                "name": "finpulse-synthetic-filings-v1",
                "synthetic": True,
                "counts": counts,
                "files": {
                    str(p.relative_to(out_dir)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files
                },
            },
            indent=2,
        )
        + "\n"
    )
    return counts


def _slug(name: str) -> str:
    return "".join(c.lower() if c.isalnum() else "-" for c in name).strip("-").replace("--", "-")
