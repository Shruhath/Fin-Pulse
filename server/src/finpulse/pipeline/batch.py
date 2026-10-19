"""Run the whole pipeline over the corpus, phase by phase, with one model on the GPU at a time.

Order (docs/PLAN.md section 3.2):
  parse, dedup, link, events (rules)      CPU
  sentiment, embed                        encoders on the GPU, then freed
  events-llm                              Qwen through Ollama, alone on the GPU, then unloaded
  summaries                               Llama through Ollama, alone on the GPU, then unloaded
  verify                                  embeddings of the claims and the NLI model, then freed

A phase that cannot run (Ollama down, a model not pulled, the neural extra not installed) is
reported as skipped with the reason and the run goes on; a phase that raises is reported failed and
stops the run, because later phases depend on it.
"""

from __future__ import annotations

import contextlib
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass

from finpulse.core.settings import get_settings
from finpulse.db.session import session_scope
from finpulse.llm.client import LlmUnavailable, OllamaClient

log = logging.getLogger(__name__)

STAGES = (
    "parse", "dedup", "link", "events", "sentiment", "embed", "events-llm", "summaries", "verify",
)  # fmt: skip


@dataclass(slots=True)
class PhaseResult:
    stage: str
    status: str  # done | skipped | failed
    seconds: float
    note: str


class Skip(Exception):
    """A phase cannot run here; the message says why."""


def _neural() -> None:
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
    except ImportError as exc:
        raise Skip("the neural extra is not installed (uv sync --extra neural)") from exc


def _ollama(model: str) -> OllamaClient:
    client = OllamaClient()
    if not client.has_model(model):
        raise Skip(f"{model} is not available at {client.base_url} (scripts/ollama-local.sh pull)")
    return client


def _parse(limit: int | None, **_: object) -> str:
    from .parse import parse_pending

    with session_scope() as s:
        st = parse_pending(s, workers=8, limit=limit)
    return f"{st.parsed} parsed, {st.failed} failed, {st.ocr_documents} read with OCR"


def _dedup(**_: object) -> str:
    from .dedup import dedup_documents

    with session_scope() as s:
        total, dupes = dedup_documents(s)
    return f"{total} documents, {dupes} near-duplicates"


def _link(limit: int | None, **_: object) -> str:
    from .link import link_pending

    with session_scope() as s:
        st = link_pending(s, limit=limit)
    return f"{st.documents} documents, {st.mentions} mentions, {st.created_entities} new entities"


def _ner(limit: int | None, device: str, **_: object) -> str:
    from .ner import load_ner_model, ner_pending

    model = load_ner_model(device=device)
    if model is None:
        raise Skip("no NER model has been trained (finpulse ner train)")
    with session_scope() as s:
        st = ner_pending(s, model, limit=limit)
    return f"{st.mentions} new mentions in {st.sentences} sentences ({st.linked} linked)"


def _events(limit: int | None, **_: object) -> str:
    from .events import extract_pending

    with session_scope() as s:
        st = extract_pending(s, limit=limit)
    return f"{st.events} rule events from {st.documents} documents"


def _sentiment(limit: int | None, device: str, **_: object) -> str:
    from sqlalchemy import text

    from finpulse.neural.device import release

    from .sentiment import load_scoring_model, score_pending

    model = load_scoring_model(device=device)
    if model is None:
        raise Skip("no sentiment model has been trained (finpulse sentiment train)")
    with session_scope() as s:
        st = score_pending(s, model, limit=limit)
        s.execute(text("refresh materialized view entity_daily"))
    del model
    with contextlib.suppress(ImportError):  # release() needs torch; the TF-IDF baseline does not
        release()
    return f"{st.mentions} mentions scored by {st.version}"


def _embed(limit: int | None, device: str, **_: object) -> str:
    _neural()
    from finpulse.embed.encoder import Embedder
    from finpulse.neural.device import release

    from .embed import embed_pending

    encoder = Embedder(device=device)
    try:
        with session_scope() as s:
            st = embed_pending(s, encoder, limit=limit)
    finally:
        del encoder
        release()
    return f"{st.sentences} sentences embedded"


def _events_llm(limit: int | None, **_: object) -> str:
    from .llm_events import llm_extract_pending

    model = get_settings().event_model
    client = _ollama(model)
    try:
        with session_scope() as s:
            st = llm_extract_pending(s, client, model, limit=limit)
    finally:
        client.unload(model)
    schema = f", {st.invalid} failing their schema" if st.invalid else ""
    return (
        f"{st.events} events from {st.documents} documents "
        f"({st.failed} failed{schema}, {st.seconds:.0f}s of model time)"
    )


def _summaries(limit: int | None, window: str, top: int, **_: object) -> str:
    from .summaries import summarize_documents, summarize_entities

    model = get_settings().summary_model
    client = _ollama(model)
    try:
        with session_scope() as s:
            docs = summarize_documents(s, client, model, limit=limit)
        with session_scope() as s:
            ents = summarize_entities(s, client, model, window=window, top=top)
    finally:
        client.unload(model)
    failed = docs.failed + ents.failed
    return f"{docs.summaries} document and {ents.summaries} company summaries, {failed} failed"


def _verify(limit: int | None, device: str, **_: object) -> str:
    _neural()
    from finpulse.embed.encoder import Embedder
    from finpulse.neural.device import release
    from finpulse.verify.nli import Nli

    from .verify import verify_pending

    judge = Nli(device=device)
    encoder = Embedder(device=device)
    try:
        with session_scope() as s:
            st = verify_pending(s, judge, encoder, limit=limit)
    finally:
        del judge, encoder
        release()
    return (
        f"{st.claims} claims: {st.entailed} entailed, {st.contradicted} contradicted, "
        f"{st.unverified} unverified"
    )


_RUNNERS: dict[str, Callable[..., str]] = {
    "parse": _parse, "dedup": _dedup, "link": _link, "ner": _ner, "events": _events, "sentiment": _sentiment,
    "embed": _embed, "events-llm": _events_llm, "summaries": _summaries, "verify": _verify,
}  # fmt: skip


def run_pipeline(
    stages: tuple[str, ...] = STAGES,
    *,
    limit: int | None = None,
    device: str = "auto",
    window: str = "365d",
    top: int = 25,
    report: Callable[[PhaseResult], None] | None = None,
) -> list[PhaseResult]:
    unknown = [s for s in stages if s not in _RUNNERS]
    if unknown:
        raise ValueError(f"unknown stage(s): {', '.join(unknown)}")
    results: list[PhaseResult] = []
    for stage in sorted(stages, key=STAGES.index):
        t0 = time.monotonic()
        try:
            note = _RUNNERS[stage](limit=limit, device=device, window=window, top=top)
            result = PhaseResult(stage, "done", time.monotonic() - t0, note)
        except (Skip, LlmUnavailable) as exc:
            result = PhaseResult(stage, "skipped", time.monotonic() - t0, str(exc))
        except Exception as exc:
            log.exception("stage %s failed", stage)
            result = PhaseResult(stage, "failed", time.monotonic() - t0, f"{type(exc).__name__}: {exc}")
        results.append(result)
        if report:
            report(result)
        if result.status == "failed":
            break
    return results
