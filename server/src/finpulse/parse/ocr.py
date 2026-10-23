"""Tesseract OCR for scanned pages. Local only: nothing leaves the machine."""

from __future__ import annotations

import os
import shutil
import subprocess
from functools import lru_cache


class OcrUnavailable(RuntimeError):
    """A scanned page needs OCR but Tesseract is not installed."""


@lru_cache
def tesseract_version() -> str | None:
    exe = shutil.which("tesseract")
    if exe is None:
        return None
    out = subprocess.run([exe, "--version"], capture_output=True, text=True, check=False)
    first = (out.stdout or out.stderr).splitlines()[0] if (out.stdout or out.stderr) else ""
    return first.removeprefix("tesseract ").strip() or None


def ocr_png(png: bytes, *, lang: str = "eng", psm: int = 3, timeout: int = 300) -> str:
    """Recognise one page image (PNG bytes) and return its text."""
    exe = shutil.which("tesseract")
    if exe is None:
        raise OcrUnavailable("tesseract is not installed; scanned pages cannot be read")
    env = {**os.environ, "OMP_THREAD_LIMIT": "1"}  # parallelism comes from the caller, per page
    proc = subprocess.run(
        [exe, "stdin", "stdout", "-l", lang, "--psm", str(psm)],
        input=png,
        capture_output=True,
        timeout=timeout,
        env=env,
        check=True,
    )
    return proc.stdout.decode("utf-8", errors="replace")
