"""Evaluation results, exactly as the harness recorded them."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from finpulse.api import schemas as s
from finpulse.api.deps import get_db
from finpulse.db.models import EvalResult

router = APIRouter()


@router.get("/eval", response_model=s.EvalReport)
def evaluation(db: Annotated[Session, Depends(get_db)]) -> s.EvalReport:
    latest: dict[tuple[str, str, str], EvalResult] = {}
    for row in db.scalars(select(EvalResult).order_by(desc(EvalResult.created_at), desc(EvalResult.id))):
        latest.setdefault((row.stage, row.model, row.dataset), row)  # newest run of each model and dataset
    results = sorted(latest.values(), key=lambda r: (r.stage, r.baseline, r.model, r.dataset))
    rows = [
        s.MetricRow(
            task=r.stage,
            model=r.model,
            baseline=r.baseline,
            dataset=r.dataset,
            indian=r.indian,
            metrics={k: float(v) for k, v in r.metrics.items()},
            p_value_vs_baseline=((r.detail or {}).get("mcnemar_vs_tfidf") or {}).get("p_value"),
            git_sha=r.git_sha,
            created_at=r.created_at,
        )
        for r in results
    ]
    with_detail = [r for r in results if r.stage == "sentiment" and r.detail]
    shown = min(
        with_detail, key=lambda r: (r.baseline, not r.indian), default=None
    )  # the proposed model first
    confusion = reliability = None
    if shown is not None:
        confusion = s.Confusion(
            model=shown.model,
            dataset=shown.dataset,
            labels=shown.detail["labels"],
            matrix=shown.detail["confusion"],
        )
        calibrated = "reliability_before" in shown.detail
        reliability = s.Reliability(
            model=shown.model,
            dataset=shown.dataset,
            before=[
                s.ReliabilityBin(**b)
                for b in shown.detail["reliability_before" if calibrated else "reliability"]
            ],
            after=[s.ReliabilityBin(**b) for b in shown.detail["reliability"]] if calibrated else None,
            ece_before=float(shown.metrics["ece_before" if calibrated else "ece"]),
            ece_after=float(shown.metrics["ece"]) if calibrated else None,
        )
    return s.EvalReport(
        generated_at=max((r.created_at for r in results), default=None),
        rows=rows,
        confusion=confusion,
        reliability=reliability,
        agreement=[],
    )
