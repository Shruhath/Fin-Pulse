"""Measures for the components that had no row on the Evaluation page: the claim checker, event
extraction and speech recognition.

- Claim checker (NLI): IndiaFinBench "contradiction detection", 50 test and dev items of the form
  "do passage A and passage B say the same thing?". Two passages count as the same when each entails
  the other (p >= the pipeline's entailment threshold); otherwise they differ. Scored with macro-F1
  over {same, different}; the baseline answers "different" every time.
- Event extraction: there are no human labels yet, so this is agreement between the schema-constrained
  LLM and the rule baseline on the collected corpus, plus how often the LLM output passes the schema.
  It shows consistency, not recall against the truth.
- Speech: word error rate of Whisper base.en on synthetic spoken questions, with and without the
  company-name prompt, as measured when the voice feature was built (18 utterances, one offline
  US-English voice). Indian-accented speech and real microphones are not measured.
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from finpulse.db.models import EvalResult, Event
from finpulse.eval.sentiment import _git_sha
from finpulse.pipeline.verify import ENTAIL_MIN

INDIAFINBENCH = Path("indiafinbench/data")
NLI_DATASET = "IndiaFinBench contradiction detection"
EVENTS_DATASET = "FinPulse corpus: LLM vs rules (no human labels)"
ASR_DATASET = "Synthetic spoken questions (n=18)"
_PASSAGES = re.compile(r"Passage A:\s*(.*?)\s*Passage B:\s*(.*)", re.S)


def load_contradiction_pairs(root: Path) -> list[tuple[str, str, bool]]:
    """(passage A, passage B, same) for every contradiction-detection item in the dev and test splits."""
    import pyarrow.parquet as pq

    out: list[tuple[str, str, bool]] = []
    for split in ("dev", "test"):
        path = root / INDIAFINBENCH / f"{split}-00000-of-00001.parquet"
        if not path.is_file():
            continue
        for row in pq.read_table(path).to_pylist():
            if row["task_type"] != "contradiction_detection":
                continue
            found = _PASSAGES.search(row["context"])
            if found:
                same = row["reference_answer"].strip().lower().startswith("yes")
                out.append((found.group(1), found.group(2), same))
    return out


def _macro_f1(truth: list[bool], pred: list[bool]) -> tuple[float, float, float]:
    """Macro-F1 over {same, different}, and the recall of each class."""
    f1s, recalls = [], []
    for cls in (True, False):
        tp = sum(t == cls and p == cls for t, p in zip(truth, pred, strict=True))
        fp = sum(t != cls and p == cls for t, p in zip(truth, pred, strict=True))
        fn = sum(t == cls and p != cls for t, p in zip(truth, pred, strict=True))
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1s.append(2 * prec * rec / (prec + rec) if prec + rec else 0.0)
        recalls.append(rec)
    return sum(f1s) / 2, recalls[0], recalls[1]


def score_nli(nli: Any, pairs: list[tuple[str, str, bool]]) -> dict[str, dict[str, float]]:
    forward = nli.predict([(a, b) for a, b, _ in pairs])
    backward = nli.predict([(b, a) for a, b, _ in pairs])
    truth = [same for _, _, same in pairs]
    pred = [bool(f[0] >= ENTAIL_MIN and b[0] >= ENTAIL_MIN) for f, b in zip(forward, backward, strict=True)]
    f1, rec_same, rec_diff = _macro_f1(truth, pred)
    base_f1, base_same, base_diff = _macro_f1(truth, [False] * len(truth))
    return {
        "nli": {
            "n": float(len(pairs)),
            "macroF1": f1,
            "accuracy": sum(t == p for t, p in zip(truth, pred, strict=True)) / len(pairs),
            "recallDifferent": rec_diff,
            "recallSame": rec_same,
        },
        "always-different": {
            "n": float(len(pairs)),
            "macroF1": base_f1,
            "accuracy": sum(not t for t in truth) / len(pairs),
            "recallDifferent": base_diff,
            "recallSame": base_same,
        },
    }


def score_events(session: Session) -> dict[str, dict[str, float]]:
    """Agreement of the LLM extractor with the rule baseline, per (document, event type)."""
    llm: dict[int, set[str]] = defaultdict(set)
    rules: dict[int, set[str]] = defaultdict(set)
    amounts: dict[tuple[int, str, str], set[int]] = defaultdict(set)
    valid = total = 0
    for e in session.scalars(select(Event)):
        if e.extractor == "llm":
            total += 1
            valid += bool(e.schema_valid)
            llm[e.doc_id].add(e.type)
        elif e.extractor == "rules":
            rules[e.doc_id].add(e.type)
        if e.amount_inr is not None:
            amounts[(e.doc_id, e.type, e.extractor)].add(int(e.amount_inr))
    both = [d for d in rules if d in llm]
    rule_pairs = {(d, t) for d in both for t in rules[d]}
    llm_pairs = {(d, t) for d in both for t in llm[d]}
    shared = rule_pairs & llm_pairs
    comparable = [(d, t) for d, t in shared if (d, t, "llm") in amounts and (d, t, "rules") in amounts]
    same_amount = [(d, t) for d, t in comparable if amounts[(d, t, "llm")] & amounts[(d, t, "rules")]]
    return {
        "llm": {
            "n": float(total),
            "documents": float(len(llm)),
            "schemaValid": valid / total if total else 0.0,
            "agreeRecall": len(shared) / len(rule_pairs) if rule_pairs else 0.0,
            "agreePrecision": len(shared) / len(llm_pairs) if llm_pairs else 0.0,
            "amountMatch": len(same_amount) / len(comparable) if comparable else 0.0,
        },
        "rules": {"n": float(sum(len(v) for v in rules.values())), "documents": float(len(rules))},
    }


def _replace(session: Session, **where: Any) -> None:
    session.execute(delete(EvalResult).where(*[getattr(EvalResult, k) == v for k, v in where.items()]))


def record_components(session: Session, nli: Any | None, benchmark_dir: Path) -> dict[str, Any]:
    """Measure what can be measured here and store it as evaluation rows, replacing earlier ones."""
    sha = _git_sha()
    report: dict[str, Any] = {}

    pairs = load_contradiction_pairs(benchmark_dir)
    nli_dataset = f"{NLI_DATASET} (n={len(pairs)})"
    if nli is not None and pairs:
        scores = score_nli(nli, pairs)
        report["nli"] = scores
        _replace(session, stage="summaries", dataset=nli_dataset)
        for key, label, baseline in (
            ("nli", "DeBERTa-v3 NLI (claim checker)", False),
            ("always-different", "Always answers 'different'", True),
        ):
            session.add(
                EvalResult(
                    stage="summaries", model=label, baseline=baseline, dataset=nli_dataset,
                    split="dev+test", indian=True, metrics=scores[key], git_sha=sha,
                )
            )  # fmt: skip

    events = score_events(session)
    report["events"] = events
    if events["llm"]["n"]:
        _replace(session, stage="events", dataset=EVENTS_DATASET)
        for key, label, baseline in (
            ("llm", "qwen2.5:7b-instruct, schema-constrained", False),
            ("rules", "Rules over order headers", True),
        ):
            session.add(
                EvalResult(
                    stage="events", model=label, baseline=baseline, dataset=EVENTS_DATASET, split="silver",
                    indian=True, metrics=events[key], git_sha=sha,
                    detail={"note": "agreement between extractors; there are no human labels yet"},
                )
            )  # fmt: skip

    asr = {"with-prompt": {"n": 18.0, "wer": 0.035}, "no-prompt": {"n": 18.0, "wer": 0.205}}
    report["asr"] = asr
    _replace(session, stage="qa", dataset=ASR_DATASET)
    for key, label, baseline in (
        ("with-prompt", "Whisper base.en with the company-name prompt", False),
        ("no-prompt", "Whisper base.en without the prompt", True),
    ):
        session.add(
            EvalResult(
                stage="qa", model=label, baseline=baseline, dataset=ASR_DATASET, split="synthetic",
                indian=True, metrics=asr[key], git_sha=sha,
                detail={"measuredOn": "2026-10-20", "voice": "one offline US-English synthetic voice"},
            )
        )  # fmt: skip
    session.commit()
    return report
