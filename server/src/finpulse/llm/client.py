"""A small client for a local Ollama server.

Only local models are used: nothing here talks to a hosted API. Requests are deterministic
(temperature 0, fixed seed) and cached on disk by a hash of everything that influences the
answer, so re-running a stage over the same documents costs nothing. JSON-schema `format`
makes the server constrain decoding to the schema.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from finpulse.core.settings import get_settings

log = logging.getLogger(__name__)


class LlmUnavailable(RuntimeError):
    """The server is not reachable or the model is not installed: a stage should skip, not crash."""


class LlmError(RuntimeError):
    """The server answered, but not with something usable."""


@dataclass(frozen=True, slots=True)
class Reply:
    text: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    seconds: float
    cached: bool = False

    def json(self) -> Any:
        try:
            return json.loads(self.text)
        except json.JSONDecodeError as exc:
            raise LlmError(f"the model returned invalid JSON: {exc}") from exc


class Llm(Protocol):
    """What the stages need from a model server; tests substitute a fake."""

    def chat(
        self,
        model: str,
        system: str,
        user: str,
        *,
        schema: dict[str, Any] | None = None,
        num_predict: int = 1024,
    ) -> Reply: ...


class OllamaClient:
    def __init__(
        self,
        base_url: str | None = None,
        *,
        timeout: float = 600.0,
        cache_dir: Path | None = None,
        transport: httpx.BaseTransport | None = None,
        num_ctx: int = 8192,
    ):
        cfg = get_settings()
        self.base_url = (base_url or cfg.ollama_url).rstrip("/")
        self.cache_dir = cache_dir if cache_dir is not None else cfg.data_dir / "cache" / "llm"
        self.num_ctx = num_ctx
        self._http = httpx.Client(base_url=self.base_url, timeout=timeout, transport=transport)

    # ------------------------------------------------------------------ server state

    def models(self) -> list[str]:
        try:
            resp = self._http.get("/api/tags", timeout=5.0)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise LlmUnavailable(f"no Ollama server at {self.base_url}") from exc
        return [m["name"] for m in resp.json().get("models", [])]

    def has_model(self, model: str) -> bool:
        try:
            return any(name == model or name.split(":")[0] == model for name in self.models())
        except LlmUnavailable:
            return False

    def unload(self, model: str) -> None:
        """Free the GPU: one model at a time is the memory budget."""
        try:
            self._http.post("/api/generate", json={"model": model, "keep_alive": 0}, timeout=30.0)
        except httpx.HTTPError:
            log.warning("could not unload %s", model)

    # ------------------------------------------------------------------ chat

    def _key(self, payload: dict[str, Any]) -> str:
        return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

    def _cache_path(self, key: str) -> Path:
        return self.cache_dir / key[:2] / f"{key}.json"

    @retry(
        retry=retry_if_exception_type((httpx.TransportError, httpx.ReadTimeout)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, max=8),
        reraise=True,
    )
    def _post(self, payload: dict[str, Any]) -> httpx.Response:
        return self._http.post("/api/chat", json=payload)

    def chat(
        self,
        model: str,
        system: str,
        user: str,
        *,
        schema: dict[str, Any] | None = None,
        num_predict: int = 1024,
    ) -> Reply:
        payload: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "stream": False,
            "options": {"temperature": 0, "seed": 7, "num_ctx": self.num_ctx, "num_predict": num_predict},
            "keep_alive": "10m",
        }
        if schema is not None:
            payload["format"] = schema
        key = self._key(payload)
        path = self._cache_path(key)
        if path.is_file():
            blob = json.loads(path.read_text(encoding="utf-8"))
            return Reply(**{**blob, "cached": True})

        t0 = time.monotonic()
        try:
            resp = self._post(payload)
        except httpx.HTTPError as exc:
            raise LlmUnavailable(f"cannot reach Ollama at {self.base_url}: {type(exc).__name__}") from exc
        if resp.status_code == 404:
            raise LlmUnavailable(f"model {model!r} is not installed (ollama pull {model})")
        if resp.status_code >= 400:
            raise LlmError(f"Ollama answered {resp.status_code}: {resp.text[:200]}")
        body = resp.json()
        reply = Reply(
            text=body["message"]["content"],
            model=model,
            prompt_tokens=int(body.get("prompt_eval_count", 0)),
            completion_tokens=int(body.get("eval_count", 0)),
            seconds=round(time.monotonic() - t0, 2),
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        blob = {
            k: getattr(reply, k) for k in ("text", "model", "prompt_tokens", "completion_tokens", "seconds")
        }
        path.write_text(json.dumps(blob, ensure_ascii=False), encoding="utf-8")
        return reply
