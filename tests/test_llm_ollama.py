import json

import httpx
import pytest

from vigie.config import Settings
from vigie.llm.base import ChatMessage, LLMError
from vigie.llm.ollama import OllamaClient

MESSAGES = [ChatMessage("system", "règles"), ChatMessage("user", "question")]


def ndjson(*chunks: dict[str, object]) -> bytes:
    return "\n".join(json.dumps(c) for c in chunks).encode() + b"\n"


def client(handler: httpx.MockTransport) -> OllamaClient:
    return OllamaClient(
        base_url="http://ollama.test/",
        model="ministral-3:3b-instruct-2512-q4_K_M",
        num_ctx=4096,
        num_predict=400,
        temperature=0.1,
        timeout_s=120.0,
        transport=handler,
    )


def test_streams_deltas_and_reads_usage_from_the_last_chunk() -> None:
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        body = ndjson(
            {"message": {"role": "assistant", "content": "Bon"}, "done": False},
            {"message": {"role": "assistant", "content": "jour"}, "done": False},
            {
                "message": {"role": "assistant", "content": ""},
                "done": True,
                "prompt_eval_count": 42,
                "eval_count": 2,
            },
        )
        return httpx.Response(200, content=b"\n" + body)

    llm = client(httpx.MockTransport(handle))
    stream = llm.stream(MESSAGES)
    assert list(stream) == ["Bon", "jour"]
    assert stream.result.text == "Bonjour"
    assert (stream.result.tokens_in, stream.result.tokens_out) == (42, 2)

    request = seen[0]
    assert request.url.path == "/api/chat"
    payload = json.loads(request.content)
    assert payload["model"] == "ministral-3:3b-instruct-2512-q4_K_M"
    assert payload["stream"] is True
    assert payload["options"] == {"num_ctx": 4096, "num_predict": 400, "temperature": 0.1}
    assert payload["messages"][0] == {"role": "system", "content": "règles"}


def test_generate_returns_the_whole_text() -> None:
    body = ndjson({"message": {"content": "Oui."}, "done": True, "eval_count": 1})
    llm = client(httpx.MockTransport(lambda _: httpx.Response(200, content=body)))
    result = llm.generate(MESSAGES)
    assert result.text == "Oui."
    assert result.tokens_in == 0


@pytest.mark.parametrize(
    ("status", "kind"),
    [(503, "overloaded"), (500, "http"), (404, "http")],
)
def test_http_errors_are_mapped_to_a_kind(status: int, kind: str) -> None:
    llm = client(httpx.MockTransport(lambda _: httpx.Response(status, content=b"busy")))
    with pytest.raises(LLMError) as err:
        llm.generate(MESSAGES)
    assert err.value.kind == kind


def test_an_error_inside_the_stream_is_reported() -> None:
    body = ndjson({"error": "model not found"})
    llm = client(httpx.MockTransport(lambda _: httpx.Response(200, content=body)))
    with pytest.raises(LLMError) as err:
        llm.generate(MESSAGES)
    assert err.value.kind == "model"
    assert "model not found" in str(err.value)


def test_a_malformed_line_is_an_http_error() -> None:
    llm = client(httpx.MockTransport(lambda _: httpx.Response(200, content=b"{oops\n")))
    with pytest.raises(LLMError) as err:
        llm.generate(MESSAGES)
    assert err.value.kind == "http"


@pytest.mark.parametrize(
    ("exc", "kind"),
    [(httpx.ReadTimeout("slow"), "timeout"), (httpx.ConnectError("down"), "unavailable")],
)
def test_transport_failures_are_mapped(exc: Exception, kind: str) -> None:
    def handle(_: httpx.Request) -> httpx.Response:
        raise exc

    with pytest.raises(LLMError) as err:
        client(httpx.MockTransport(handle)).generate(MESSAGES)
    assert err.value.kind == kind


def test_from_settings_pins_the_configured_tag() -> None:
    settings = Settings(_env_file=None)
    body = ndjson({"message": {"content": "ok"}, "done": True})
    llm = OllamaClient.from_settings(
        settings, transport=httpx.MockTransport(lambda _: httpx.Response(200, content=body))
    )
    assert llm.model == settings.ollama_model
    assert llm.generate(MESSAGES).text == "ok"
