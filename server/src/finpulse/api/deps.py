from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy.orm import Session

from finpulse.asr.whisper import Transcriber
from finpulse.db.session import get_sessionmaker

_transcriber: Transcriber | None = None


def get_db() -> Iterator[Session]:
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.close()


def get_transcriber() -> Transcriber:
    """The process-wide speech model; it loads on first use, not at start-up."""
    global _transcriber
    if _transcriber is None:
        _transcriber = Transcriber()
    return _transcriber
