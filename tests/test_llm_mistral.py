import json

import httpx
import pytest

from vigie.config import Settings
from vigie.llm.base import ChatMessage, LLMError
from vigie.llm.mistral import MistralClient

MESSAGES = [ChatMessage("user", "question")]
FAKE_KEY = "test-key-not-a-secret"


def sse(*chunks: object) -> bytes:
    lines = [f"data: {c if isinstance(c, str) else json.dumps(c)}" for c in chunks]
    return ("\n\n".join([": keep-alive", *lines]) + "\n\n").encode()


def client(transport: httpx.MockTransport) -> MistralClient:
    return MistralClient(
        api_key=FAKE_KEY,
        model="ministral-3b-latest",
        base_url="https://mistral.test",
        max_tokens=400,
        temperature=0.1,
        timeout_s=120.0,
        transport=transport,
    )


def test_is_disabled_without_a_key() -> None:
    with pytest.raises(LLMError) as err:
        MistralClient.from_settings(Settings(_env_file=None))
    assert err.value.kind == "disabled"


def test_streams_server_sent_events() -> None:
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        body = sse(
            {"choices": [{"delta": {"content": "Bon"}}]},
            {"choices": [{"delta": {"content": None}}]},
            {
                "choices": [{"delta": {"content": "jour"}}],
                "usage": {"prompt_tokens": 7, "completion_tokens": 2},
            },
            "[DONE]",
            {"choices": [{"delta": {"content": "ignored"}}]},
        )
        return httpx.Response(200, content=body)

    result = client(httpx.MockTransport(handle)).generate(MESSAGES)
    assert result.text == "Bonjour"
    assert (result.tokens_in, result.tokens_out) == (7, 2)
    assert seen[0].url.path == "/v1/chat/completions"
    assert seen[0].headers["Authorization"] == f"Bearer {FAKE_KEY}"
    payload = json.loads(seen[0].content)
    assert payload["max_tokens"] == 400
    assert payload["stream"] is True


def test_from_settings_uses_the_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIGIE_MISTRAL_API_KEY", FAKE_KEY)
    llm = MistralClient.from_settings(Settings(_env_file=None))
    assert llm.model == "ministral-3b-latest"


@pytest.mark.parametrize(("status", "kind"), [(429, "overloaded"), (401, "http")])
def test_http_errors_are_mapped(status: int, kind: str) -> None:
    llm = client(httpx.MockTransport(lambda _: httpx.Response(status, content=b"no")))
    with pytest.raises(LLMError) as err:
        llm.generate(MESSAGES)
    assert err.value.kind == kind


def test_malformed_event_is_an_http_error() -> None:
    llm = client(httpx.MockTransport(lambda _: httpx.Response(200, content=b"data: {x\n\n")))
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


def test_stream_without_done_marker_still_ends() -> None:
    body = sse({"choices": [{"delta": {"content": "fin"}}]})
    llm = client(httpx.MockTransport(lambda _: httpx.Response(200, content=body)))
    assert llm.generate(MESSAGES).text == "fin"
