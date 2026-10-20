"""Speech to text with a Whisper model run on this machine.

The audio never leaves the process and is not stored. The model is loaded from the local Hugging Face
cache only (`scripts/fetch_models.py asr`), so a missing model is reported, not silently downloaded.
Whisper accepts a short prompt that steers its spelling, so each request carries the names of the
companies the corpus mentions most: "Rajesh Exports" is then heard as such and not as "Rajesh Express".
"""

from __future__ import annotations

import logging
import re
import threading
import time
from dataclasses import dataclass
from typing import Any

import numpy as np

from finpulse.core.settings import get_settings

log = logging.getLogger(__name__)

MAX_PROMPT_CHARS = 500  # Whisper reads at most 224 prompt tokens


class TranscriberUnavailable(RuntimeError):
    """The speech model is not installed or its libraries are missing."""


@dataclass(frozen=True, slots=True)
class Transcript:
    text: str
    seconds: float
    model: str


def installed(name: str | None = None) -> bool:
    """Is the speech model in the local cache? Cheap: it imports no model library."""
    try:
        from huggingface_hub import try_to_load_from_cache
    except ImportError:
        return False
    found = try_to_load_from_cache(name or get_settings().asr_model, "config.json")
    return isinstance(found, str)


_HEAD = "A question about SEBI, NCLT and RBI filings, such as a penalty of Rs. 25 lakh or Rs. 4,39,725."


def build_prompt(names: list[str]) -> str:
    """A prompt that sounds like the questions asked, followed by the names to spell correctly."""
    head = _HEAD
    tail = " Companies: " + ", ".join(names) + "." if names else ""
    return (head + tail)[:MAX_PROMPT_CHARS]


def clean_text(text: str, prompt: str | None) -> str:
    """Drop what Whisper does with a poor recording: repeating a phrase, or reading the prompt back."""
    sentences = [x for x in re.split(r"(?<=[.?!])\s+", " ".join(text.split())) if x]
    kept: list[str] = []
    for sentence in sentences:
        if kept and sentence == kept[-1]:
            continue  # the same sentence again
        kept.append(sentence)
    cleaned = " ".join(kept)
    words = re.findall(r"[a-z0-9]+", cleaned.lower())
    if len(words) >= 6 and len(set(words)) / len(words) < 0.4:
        return ""  # "NCLT, NCLT, NCLT, ...": the model looping on noise
    if prompt and (cleaned in prompt or cleaned.startswith(_HEAD[:30])):
        return ""  # nothing but the prompt: the audio held no speech it could use
    return cleaned


class Transcriber:
    """One Whisper pipeline, loaded on first use and shared; transcriptions run one at a time."""

    def __init__(self, name: str | None = None):
        self.name = name or get_settings().asr_model
        self._pipe: Any = None
        self._lock = threading.Lock()

    def _load(self) -> Any:
        if self._pipe is not None:
            return self._pipe
        if not installed(self.name):
            raise TranscriberUnavailable(
                f"the speech model {self.name} is not installed "
                "(uv run python ../scripts/fetch_models.py asr)"
            )
        try:
            import torch
            from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline
        except ImportError as exc:
            raise TranscriberUnavailable(
                "the neural extra is not installed (uv sync --extra neural)"
            ) from exc
        t0 = time.monotonic()
        # CPU: the GPU belongs to the language model. float32 keeps the output identical to the reference.
        model = AutoModelForSpeechSeq2Seq.from_pretrained(
            self.name, dtype=torch.float32, local_files_only=True
        )
        processor = AutoProcessor.from_pretrained(self.name, local_files_only=True)
        self._pipe = pipeline(
            "automatic-speech-recognition",
            model=model,
            tokenizer=processor.tokenizer,
            feature_extractor=processor.feature_extractor,
            device="cpu",
        )
        log.info("loaded %s in %.1fs", self.name, time.monotonic() - t0)
        return self._pipe

    def transcribe(self, samples: np.ndarray, prompt: str | None = None) -> Transcript:
        t0 = time.monotonic()
        with self._lock:
            pipe = self._load()
            # an English-only model (*.en) rejects task and language; a multilingual one is told English
            kwargs: dict[str, Any] = (
                {} if self.name.endswith(".en") else {"task": "transcribe", "language": "en"}
            )
            if prompt:
                kwargs["prompt_ids"] = pipe.tokenizer.get_prompt_ids(prompt, return_tensors="pt")
            kwargs["max_new_tokens"] = min(
                200, 16 + int(10 * len(samples) / 16_000)
            )  # about 4 tokens a second spoken
            out = pipe(
                {"raw": samples, "sampling_rate": 16_000},
                chunk_length_s=30,
                generate_kwargs=kwargs,
            )
        text = clean_text(str(out["text"]), prompt)
        return Transcript(text=text, seconds=round(time.monotonic() - t0, 2), model=self.name)
