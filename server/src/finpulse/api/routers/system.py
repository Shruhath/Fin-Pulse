"""Health and configuration, for the status bar and the settings view."""

from __future__ import annotations

import shutil
import subprocess
from functools import lru_cache
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func, select, text
from sqlalchemy.orm import Session

from finpulse.api import queries as q
from finpulse.api import schemas as s
from finpulse.api.deps import get_db
from finpulse.core.settings import get_settings
from finpulse.db.models import Job, Run
from finpulse.parse import tesseract_version

router = APIRouter()
Db = Annotated[Session, Depends(get_db)]


@lru_cache
def gpu_name() -> str | None:
    exe = shutil.which("nvidia-smi")
    if exe is None:
        return None
    try:
        out = subprocess.run(
            [exe, "--query-gpu=name,memory.total", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip().splitlines()[0] if out.stdout.strip() else None


def ollama_models() -> list[str] | None:
    """Names of the models the local server has, or None when it does not answer."""
    try:
        resp = httpx.get(f"{get_settings().ollama_url}/api/tags", timeout=0.8)
        resp.raise_for_status()
        return [m["name"] for m in resp.json().get("models", [])]
    except (httpx.HTTPError, ValueError, KeyError):
        return None


@router.get("/health", response_model=s.Health)
def health(db: Db) -> s.Health:
    try:
        db.execute(text("select 1"))
        database = True
    except Exception:
        database = False
    queued = db.scalar(select(func.count()).select_from(Job).where(Job.status == "queued")) if database else 0
    models = ollama_models()
    return s.Health(
        status="ok" if database else "degraded",
        database=database,
        ollama=models is not None,
        ollama_models=models or [],
        gpu=gpu_name(),
        tesseract=tesseract_version(),
        sentiment_model=q.active_model(db) if database else None,
        queued_jobs=queued or 0,
    )


@router.get("/runs", response_model=list[s.RunRecord])
def runs(
    db: Db,
    stage: Annotated[str | None, Query(max_length=24)] = None,
    status: Annotated[str | None, Query(pattern="^(running|done|failed)$")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[s.RunRecord]:
    stmt = select(Run).order_by(desc(Run.started_at), desc(Run.id)).limit(limit)
    if stage:
        stmt = stmt.where(Run.stage == stage)
    if status:
        stmt = stmt.where(Run.status == status)
    return [
        s.RunRecord(
            id=str(r.id),
            stage=r.stage,
            model=r.model,
            prompt_version=r.prompt_version,
            params=r.params,
            status=r.status,
            started_at=r.started_at,
            latency_ms=r.latency_ms,
            error=r.error,
        )
        for r in db.scalars(stmt)
    ]


@router.get("/pipeline/config", response_model=s.PipelineConfig)
def pipeline_config(db: Db) -> s.PipelineConfig:
    cfg = get_settings()
    return s.PipelineConfig(
        sentiment_model=q.active_model(db),
        event_model=cfg.event_model,
        summary_model=cfg.summary_model,
        score_band=q.SCORE_BAND,
        ocr_dpi=cfg.ocr_dpi,
        ocr_min_words_per_page=cfg.ocr_min_words_per_page,
    )
