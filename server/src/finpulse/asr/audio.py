"""Spoken audio as the transcriber needs it: mono float32 at 16 kHz.

The web app sends 16 kHz mono 16-bit WAV, so the usual path is a straight copy. Other PCM WAV files are
accepted too (mixed down and resampled) so the endpoint works from a script. Compressed audio is not:
decoding it would need a codec library, and the browser can produce WAV itself.
"""

from __future__ import annotations

import io
import wave

import numpy as np

SAMPLE_RATE = 16_000
MAX_SECONDS = 60
MAX_BYTES = 12 * 1024 * 1024  # a minute of 44.1 kHz stereo 16-bit is about 10 MB
SILENCE_PEAK = 0.01  # below this the recording holds no speech (about -40 dBFS)


class AudioError(ValueError):
    """The upload is not audio the transcriber can use; the message says why."""


def _resample(samples: np.ndarray, rate: int) -> np.ndarray:
    if rate == SAMPLE_RATE:
        return samples
    if (
        rate > SAMPLE_RATE
    ):  # average over the samples that collapse into one, a cheap low-pass against aliasing
        width = max(1, round(rate / SAMPLE_RATE))
        usable = len(samples) - len(samples) % width
        samples = samples[:usable].reshape(-1, width).mean(axis=1)
        rate = rate / width
    target = round(len(samples) * SAMPLE_RATE / rate)
    if target == 0:
        return samples[:0]
    return np.interp(np.linspace(0, len(samples) - 1, target), np.arange(len(samples)), samples).astype(
        np.float32
    )


def decode_wav(data: bytes) -> np.ndarray:
    """PCM WAV bytes to mono float32 samples at 16 kHz in [-1, 1]."""
    if len(data) > MAX_BYTES:
        raise AudioError("the recording is too large")
    try:
        with wave.open(io.BytesIO(data)) as wav:
            channels, width, rate, frames = (
                wav.getnchannels(),
                wav.getsampwidth(),
                wav.getframerate(),
                wav.getnframes(),
            )
            if frames / max(rate, 1) > MAX_SECONDS:
                raise AudioError(f"the recording is longer than {MAX_SECONDS} seconds")
            raw = wav.readframes(frames)
    except (wave.Error, EOFError) as exc:
        raise AudioError("send a PCM WAV recording (audio/wav)") from exc
    if width == 2:
        samples = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    elif width == 4:
        samples = np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2147483648.0
    elif width == 1:
        samples = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    else:
        raise AudioError("only 8, 16 and 32-bit PCM WAV is supported")
    if channels > 1:
        samples = samples[: len(samples) - len(samples) % channels].reshape(-1, channels).mean(axis=1)
    return _resample(samples, rate).astype(np.float32)


def has_speech(samples: np.ndarray) -> bool:
    """False for silence or a dead microphone, which a speech model would otherwise "hear" words in."""
    return bool(len(samples) >= SAMPLE_RATE // 5 and float(np.max(np.abs(samples))) >= SILENCE_PEAK)
