"""Score every stage against the gold passages and record the results.

Writes one `eval_results` row per model and task with dataset "FinPulse gold" (the Indian slice), and
a JSON file under `ml/results/gold/`. Nothing here runs unless gold annotations exist: an empty gold
set records nothing, so a number can never appear without human labels behind it.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from finpulse.core.settings import REPO_DIR, get_settings
from finpulse.db.models import Annotation, EvalResult, Run
from finpulse.llm.client import Llm
from finpulse.pipeline.runs import recorded_run
from finpulse.pipeline.verify import Judge

from .gold import evaluate_events, evaluate_ner, sentiment_examples
from .sentiment import SpanModel, evaluate
from .summaries import evaluate_summaries

DATASET = "FinPulse gold"


@dataclass(slots=True)
class GoldRun:
    rows: list[dict[str, Any]]
    path: Path | None


def _git_sha() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO_DIR, capture_output=True, text=True, check=True
        )
        return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def gold_counts(session: Session) -> dict[str, int]:
    rows = session.execute(
        select(Annotation.task, func.count())
        .where(Annotation.label_source == "gold")
        .group_by(Annotation.task)
    )
    return {task: n for task, n in rows}


def run_gold_eval(
    session: Session,
    *,
    scorer: SpanModel | None = None,
    llm: Llm | None = None,
    llm_model: str | None = None,
    judge: Judge | None = None,
) -> GoldRun:
    counts = gold_counts(session)
    if not counts:
        return GoldRun([], None)
    rows: list[dict[str, Any]] = []

    def add(
        stage: str,
        model: str,
        baseline: bool,
        metrics: dict[str, float],
        detail: dict[str, Any] | None = None,
    ) -> None:
        rows.append(
            {
                "stage": stage,
                "model": model,
                "baseline": baseline,
                "dataset": DATASET,
                "metrics": metrics,
                "detail": detail,
            }
        )

    with recorded_run(session, "eval-gold", params={"gold_annotations": counts}) as run:
        if "event" in counts:
            add("events", "Rules over operative sentences", True, evaluate_events(session, "rules"))
            llm_ran = session.scalar(
                select(Run.id).where(Run.stage == "events-llm", Run.status == "done").limit(1)
            )
            if llm_ran is not None:  # a zero-recall row for an extractor that never ran would mislead
                llm_metrics = evaluate_events(session, "llm")
                add(
                    "events",
                    f"{llm_model or get_settings().event_model}, schema-constrained",
                    False,
                    llm_metrics,
                )
        if "ner" in counts:
            add("ner", "Gazetteer rules + title parties", True, evaluate_ner(session))
        if "sentiment" in counts and scorer is not None:
            examples = sentiment_examples(session)
            if examples:
                result = evaluate(scorer, examples)
                add("sentiment", str(scorer.version), False, result["metrics"], result["detail"])
        if "summary" in counts and llm is not None:
            scores = evaluate_summaries(session, llm, llm_model or get_settings().summary_model, judge)
            for name, label, baseline in (
                ("llm", f"{llm_model or get_settings().summary_model} + NLI check", False),
                ("lead3", "Lead-3", True),
                ("lexrank", "LexRank (extractive)", True),
            ):
                add("summaries", label, baseline, scores[name])

        sha = _git_sha()
        for row in rows:
            session.add(
                EvalResult(
                    stage=row["stage"],
                    model=row["model"],
                    baseline=row["baseline"],
                    dataset=DATASET,
                    split="test",
                    indian=True,
                    metrics=row["metrics"],
                    detail=row["detail"],
                    run_id=run.id,
                    git_sha=sha,
                )
            )
    out = get_settings().results_dir / "gold"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{datetime.now(UTC):%Y%m%dT%H%M%S}.json"
    path.write_text(
        json.dumps({"git_sha": sha, "gold_annotations": counts, "rows": rows}, indent=2, default=str) + "\n"
    )
    return GoldRun(rows, path)
