import io
import wave
from datetime import date

import numpy as np
import pytest

from finpulse.api.app import app
from finpulse.api.deps import get_transcriber
from finpulse.asr import vocabulary
from finpulse.asr.audio import MAX_SECONDS, SAMPLE_RATE, AudioError, decode_wav, has_speech
from finpulse.asr.whisper import Transcriber, TranscriberUnavailable, Transcript, build_prompt, clean_text
from finpulse.db.models import Document, Entity, Mention


def wav_bytes(samples, rate=SAMPLE_RATE, channels=1, width=2) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(width)
        w.setframerate(rate)
        w.writeframes((np.asarray(samples) * 32767).astype("<i2").tobytes())
    return buf.getvalue()


def tone(seconds, rate=SAMPLE_RATE, amplitude=0.3, hz=220):
    t = np.arange(int(seconds * rate)) / rate
    return (amplitude * np.sin(2 * np.pi * hz * t)).astype(np.float32)


# ------------------------------------------------------------------ audio


def test_a_16k_mono_wav_decodes_unchanged():
    samples = tone(1.0)
    out = decode_wav(wav_bytes(samples))
    assert out.dtype == np.float32 and len(out) == SAMPLE_RATE
    assert np.max(np.abs(out - samples)) < 1e-3


def test_other_rates_and_stereo_are_mixed_down_and_resampled_to_16k():
    left = tone(1.0, rate=44_100)
    stereo = np.stack([left, left], axis=1).reshape(-1)
    out = decode_wav(wav_bytes(stereo, rate=44_100, channels=2))
    assert abs(len(out) - SAMPLE_RATE) <= 2
    assert float(np.max(np.abs(out))) == pytest.approx(0.3, abs=0.05)  # the tone survives the resampling


@pytest.mark.parametrize("data", [b"", b"not audio at all", b"RIFF" + b"\x00" * 40])
def test_anything_that_is_not_pcm_wav_is_refused(data):
    with pytest.raises(AudioError):
        decode_wav(data)


def test_a_recording_over_the_limit_is_refused():
    with pytest.raises(AudioError, match="longer than"):
        decode_wav(wav_bytes(np.zeros((MAX_SECONDS + 1) * SAMPLE_RATE, dtype=np.float32)))


def test_silence_and_clips_too_short_to_hold_a_word_have_no_speech():
    assert not has_speech(np.zeros(SAMPLE_RATE, dtype=np.float32))
    assert not has_speech(tone(0.1))
    assert has_speech(tone(1.0))


# ------------------------------------------------------------------ prompt and cleanup


def test_the_prompt_names_the_companies_and_stays_within_whispers_limit():
    prompt = build_prompt(["Wipro Limited", "Rajesh Exports Limited"])
    assert "Wipro Limited" in prompt and "Rajesh Exports Limited" in prompt and "SEBI" in prompt
    assert len(build_prompt(["A Very Long Company Name Limited"] * 100)) <= 500


def test_a_looping_or_echoed_transcript_is_discarded():
    prompt = build_prompt(["Wipro Limited"])
    assert (
        clean_text("What action did SEBI take? What action did SEBI take?", prompt)
        == "What action did SEBI take?"
    )
    assert clean_text("NCLT, NCLT, NCLT, NCLT, NCLT, NCLT, NCLT, NCLT,", prompt) == ""
    assert clean_text(prompt, prompt) == ""
    assert clean_text("A question about SEBI, NCLT and RBI filings, such as", prompt) == ""
    assert clean_text("Why was Karthik Travels admitted into insolvency?", prompt) != ""


def test_a_missing_speech_model_is_reported_not_downloaded():
    with pytest.raises(TranscriberUnavailable, match="not installed"):
        Transcriber("openai/whisper-no-such-model").transcribe(tone(1.0))


# ------------------------------------------------------------------ vocabulary and API


@pytest.mark.db
def test_the_prompt_vocabulary_is_the_companies_most_filings_mention(db):
    vocabulary._cache = None
    big = Entity(slug="big-co", canonical_name="Big Company Limited")
    small = Entity(slug="small-co", canonical_name="Small Company Limited")
    person = Entity(slug="p", canonical_name="Some Person", kind="person")
    db.add_all([big, small, person])
    db.flush()
    docs = []
    for i in range(3):
        d = Document(
            source_kind="SEBI", title=f"d{i}", raw_sha256=str(i) * 64, clean_text="x", status="analysed",
            published_at=date(2026, 1, 1 + i),
        )  # fmt: skip
        docs.append(d)
    pasted = Document(source_kind="SEBI", title="p", raw_sha256="9" * 64, clean_text="x", is_submission=True)
    db.add_all([*docs, pasted])
    db.flush()
    for entity, targets in ((big, docs), (small, docs[:1]), (person, docs)):
        for d in targets:
            db.add(
                Mention(
                    doc_id=d.id, entity_id=entity.id, char_start=0, char_end=1, surface="x", ner_model="t"
                )
            )
    db.add(
        Mention(doc_id=pasted.id, entity_id=small.id, char_start=0, char_end=1, surface="x", ner_model="t")
    )
    db.flush()
    assert vocabulary.top_company_names(db) == ["Big Company Limited", "Small Company Limited"]
    vocabulary._cache = None


class FakeSpeech:
    name = "fake-whisper"

    def __init__(self, text="What action did SEBI take?", fail=None):
        self.text, self.fail, self.calls = text, fail, []

    def transcribe(self, samples, prompt=None):
        if self.fail:
            raise self.fail
        self.calls.append((len(samples), prompt))
        return Transcript(self.text, 0.4, self.name)


@pytest.fixture
def speech():
    fake = FakeSpeech()
    app.dependency_overrides[get_transcriber] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_transcriber, None)


@pytest.mark.db
def test_a_spoken_question_is_transcribed_with_the_company_vocabulary(client, db, speech):
    vocabulary._cache = None
    reply = client.post(
        "/api/transcribe", content=wav_bytes(tone(1.5)), headers={"content-type": "audio/wav"}
    )
    assert reply.status_code == 200
    assert reply.json() == {"text": "What action did SEBI take?", "seconds": 0.4, "model": "fake-whisper"}
    (length, prompt) = speech.calls[0]
    assert length == int(1.5 * SAMPLE_RATE) and "SEBI" in prompt


@pytest.mark.db
def test_silence_returns_no_text_without_asking_the_model(client, db, speech):
    reply = client.post(
        "/api/transcribe", content=wav_bytes(np.zeros(SAMPLE_RATE)), headers={"content-type": "audio/wav"}
    )
    assert reply.status_code == 200 and reply.json()["text"] == "" and speech.calls == []


@pytest.mark.db
def test_bad_uploads_and_a_missing_model_get_clear_errors(client, db, speech):
    assert client.post("/api/transcribe", content=b"mp3 bytes").status_code == 415
    big = b"RIFF" + b"\x00" * (13 * 1024 * 1024)
    assert client.post("/api/transcribe", content=big).status_code == 413
    app.dependency_overrides[get_transcriber] = lambda: FakeSpeech(
        fail=TranscriberUnavailable("not installed")
    )
    reply = client.post("/api/transcribe", content=wav_bytes(tone(1.0)))
    assert reply.status_code == 503 and "not installed" in reply.json()["detail"]


@pytest.mark.db
def test_health_says_whether_the_speech_model_is_installed(client, db, monkeypatch):
    from finpulse.api.routers import system

    monkeypatch.setattr(system, "installed", lambda: False)
    assert client.get("/api/health").json()["asrModel"] is None
    monkeypatch.setattr(system, "installed", lambda: True)
    assert client.get("/api/health").json()["asrModel"] == "openai/whisper-base.en"
