import json

import httpx
import pytest

from finpulse.llm.client import LlmError, LlmUnavailable, OllamaClient


def _client(handler, tmp_path):
    return OllamaClient("http://ollama.test", cache_dir=tmp_path, transport=httpx.MockTransport(handler))


def _chat_ok(request):
    body = json.loads(request.content)
    assert body["options"]["temperature"] == 0 and body["stream"] is False
    return httpx.Response(
        200,
        json={"message": {"content": '{"events": []}'}, "prompt_eval_count": 42, "eval_count": 7},
    )


def test_reply_is_parsed_and_cached_on_disk(tmp_path):
    calls = []

    def handler(request):
        calls.append(request)
        return _chat_ok(request)

    client = _client(handler, tmp_path)
    first = client.chat("qwen2.5:7b-instruct", "sys", "user", schema={"type": "object"})
    again = client.chat("qwen2.5:7b-instruct", "sys", "user", schema={"type": "object"})
    assert first.json() == {"events": []} and first.prompt_tokens == 42 and not first.cached
    assert again.cached and again.text == first.text
    assert len(calls) == 1  # the second answer came from disk
    other = client.chat("qwen2.5:7b-instruct", "sys", "a different question", schema={"type": "object"})
    assert not other.cached and len(calls) == 2


def test_schema_is_sent_as_the_format(tmp_path):
    seen = {}

    def handler(request):
        seen.update(json.loads(request.content))
        return _chat_ok(request)

    _client(handler, tmp_path).chat("m", "s", "u", schema={"type": "object", "properties": {}})
    assert seen["format"] == {"type": "object", "properties": {}}


def test_a_missing_model_means_unavailable_not_a_crash(tmp_path):
    client = _client(lambda r: httpx.Response(404, json={"error": "model not found"}), tmp_path)
    with pytest.raises(LlmUnavailable, match="ollama pull"):
        client.chat("nope", "s", "u")


def test_an_unreachable_server_means_unavailable(tmp_path):
    def handler(request):
        raise httpx.ConnectError("refused")

    client = _client(handler, tmp_path)
    with pytest.raises(LlmUnavailable):
        client.chat("m", "s", "u")
    assert client.has_model("m") is False


def test_server_errors_and_bad_json_are_llm_errors(tmp_path):
    with pytest.raises(LlmError, match="500"):
        _client(lambda r: httpx.Response(500, text="boom"), tmp_path).chat("m", "s", "u")
    reply = _client(lambda r: httpx.Response(200, json={"message": {"content": "not json"}}), tmp_path).chat(
        "m", "s", "u2"
    )
    with pytest.raises(LlmError, match="invalid JSON"):
        reply.json()


def test_has_model_matches_name_with_or_without_tag(tmp_path):
    client = _client(
        lambda r: httpx.Response(200, json={"models": [{"name": "qwen2.5:7b-instruct"}]}), tmp_path
    )
    assert client.has_model("qwen2.5:7b-instruct") and client.has_model("qwen2.5")
    assert not client.has_model("llama3.1:8b")
