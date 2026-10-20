"""Turn a spoken question into text, on this machine."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from finpulse.api import schemas as s
from finpulse.api.deps import get_db, get_transcriber
from finpulse.asr.audio import MAX_BYTES, AudioError, decode_wav, has_speech
from finpulse.asr.vocabulary import top_company_names
from finpulse.asr.whisper import Transcriber, TranscriberUnavailable, build_prompt

router = APIRouter()
Db = Annotated[Session, Depends(get_db)]
Speech = Annotated[Transcriber, Depends(get_transcriber)]

_AUDIO_BODY = {
    "requestBody": {
        "required": True,
        "content": {"audio/wav": {"schema": {"type": "string", "format": "binary"}}},
    }
}


@router.post("/transcribe", response_model=s.Transcription, openapi_extra=_AUDIO_BODY)
async def transcribe(request: Request, db: Db, speech: Speech) -> s.Transcription:
    """Transcribe a PCM WAV recording (16 kHz mono is what the web app sends, up to 60 seconds).

    Nothing is stored: the audio is decoded in memory and dropped. A recording with no speech in it
    returns an empty `text` instead of a guess.
    """
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_BYTES:
        raise HTTPException(413, "the recording is too large")
    data = await request.body()
    try:
        samples = decode_wav(data)
    except AudioError as exc:
        raise HTTPException(413 if "large" in str(exc) else 415, str(exc)) from exc
    if not has_speech(samples):
        return s.Transcription(text="", seconds=0.0, model=speech.name)
    prompt = build_prompt(top_company_names(db))
    try:
        out = await run_in_threadpool(speech.transcribe, samples, prompt)
    except TranscriberUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    return s.Transcription(text=out.text, seconds=out.seconds, model=out.model)
