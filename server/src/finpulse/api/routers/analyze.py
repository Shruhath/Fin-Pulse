"""Submit a document for live analysis and follow its progress."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from finpulse.api import schemas as s
from finpulse.api.deps import get_db
from finpulse.pipeline import analyze as pipeline
from finpulse.pipeline.jobs import enqueue, get_job

router = APIRouter()
Db = Annotated[Session, Depends(get_db)]
MAX_UPLOAD = 15 * 1024 * 1024


def _accepted(db: Session, payload: dict, doc_id: int | None) -> s.AnalyzeAccepted:
    job = enqueue(db, "analyze", payload, document_id=doc_id)
    db.commit()
    return s.AnalyzeAccepted(job_id=str(job.id))


@router.post("/analyze", response_model=s.AnalyzeAccepted, status_code=202)
def analyze(body: s.AnalyzeRequest, db: Db) -> s.AnalyzeAccepted:
    """Queue pasted text or a URL. Exactly one of `text` and `url` is required."""
    if bool(body.text and body.text.strip()) == bool(body.url):
        raise HTTPException(422, "send either `text` or `url`")
    if body.url:
        return _accepted(db, {"url": body.url, "source": body.source}, None)
    doc = pipeline.document_from_text(db, body.text or "", body.title, body.source)
    return _accepted(db, {"source": body.source}, doc.id)


@router.post("/analyze/file", response_model=s.AnalyzeAccepted, status_code=202)
async def analyze_file(
    db: Db,
    file: Annotated[UploadFile, File()],
    source: Annotated[s.SourceKind, Form()] = "NEWS",
) -> s.AnalyzeAccepted:
    """Queue an uploaded PDF or HTML file (up to 15 MB)."""
    data = await file.read(MAX_UPLOAD + 1)
    if not data:
        raise HTTPException(422, "the file is empty")
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "the file is larger than 15 MB")
    if data[:5] != b"%PDF-" and not (file.filename or "").lower().endswith((".html", ".htm")):
        raise HTTPException(415, "upload a PDF or an HTML file")
    doc = pipeline.document_from_bytes(db, data, file.filename or "upload.pdf", source)
    return _accepted(db, {"source": source}, doc.id)


@router.get("/jobs/{job_id}", response_model=s.Job)
def job(job_id: str, db: Db) -> s.Job:
    row = get_job(db, job_id)
    if row is None:
        raise HTTPException(404, "no such job")
    return s.Job(
        id=str(row.id),
        status=row.status,
        stages=[s.JobStage(**stage) for stage in row.stages],
        document_id=str(row.document_id) if row.document_id else None,
        error=row.error,
    )
