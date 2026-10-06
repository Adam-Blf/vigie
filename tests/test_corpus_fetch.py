from collections.abc import Callable

import httpx
import pytest

from vigie.config import Settings
from vigie.corpus.fetch import CellarClient, FetchError
from vigie.corpus.sources import get_regulation

DORA = get_regulation("DORA")
CELLAR_DOC = "http://publications.europa.eu/resource/cellar/0caf473a/DOC_1"
Handler = Callable[[httpx.Request], httpx.Response]


class FakeClock:
    """Time only moves when the code under test sleeps, so the test never waits."""

    def __init__(self) -> None:
        self.now = 100.0
        self.sleeps: list[float] = []

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds

    def __call__(self) -> float:
        return self.now


def make_client(settings: Settings, handler: Handler, clock: FakeClock) -> CellarClient:
    return CellarClient(
        settings, transport=httpx.MockTransport(handler), sleep=clock.sleep, clock=clock
    )


def cellar(requests: list[httpx.Request], *responses: httpx.Response) -> Handler:
    queue = list(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return queue.pop(0)

    return handler


def test_redirect_to_plain_http_is_followed_over_https(corpus_settings: Settings) -> None:
    requests: list[httpx.Request] = []
    handler = cellar(
        requests,
        httpx.Response(303, headers={"Location": CELLAR_DOC}),
        httpx.Response(200, content=b"<html/>"),
    )
    clock = FakeClock()
    client = make_client(corpus_settings, handler, clock)
    assert client.fetch(DORA) == b"<html/>"
    client.close()
    assert [str(r.url) for r in requests] == [
        "https://publications.europa.eu/resource/celex/32022R2554",
        CELLAR_DOC.replace("http://", "https://"),
    ]
    first = requests[0].headers
    assert first["Accept"] == "application/xhtml+xml"
    assert first["Accept-Language"] == "fra"
    assert first["User-Agent"].startswith("vigie-corpus/")
    # Two requests back to back: the second one waits for the one second slot.
    assert clock.sleeps == [1.0]


def test_second_fetch_is_served_from_the_disk_cache(corpus_settings: Settings) -> None:
    requests: list[httpx.Request] = []
    handler = cellar(requests, httpx.Response(200, content=b"<html>dora</html>"))
    client = make_client(corpus_settings, handler, FakeClock())
    client.fetch(DORA)
    assert client.fetch(DORA) == b"<html>dora</html>"
    assert len(requests) == 1
    cached = corpus_settings.corpus_cache_dir / "32022R2554.fra.xhtml"
    assert cached.read_bytes() == b"<html>dora</html>"
    assert not cached.with_suffix(".part").exists()


def test_transient_failures_are_retried_with_exponential_backoff(
    corpus_settings: Settings,
) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503)
        if calls == 2:
            raise httpx.ConnectError("reset", request=request)
        if calls == 3:
            # The EUR-Lex robot wall: 202 with nothing inside.
            return httpx.Response(202)
        if calls == 4:
            return httpx.Response(200, content=b"")
        return httpx.Response(200, content=b"<html/>")

    clock = FakeClock()
    client = make_client(corpus_settings, handler, clock)
    assert client.fetch(DORA) == b"<html/>"
    assert clock.sleeps == [2.0, 4.0, 8.0, 16.0]


def test_gives_up_after_the_configured_retries(corpus_settings: Settings) -> None:
    settings = corpus_settings.model_copy(update={"corpus_max_retries": 2})
    clock = FakeClock()
    client = make_client(settings, lambda _: httpx.Response(429), clock)
    with pytest.raises(FetchError, match=r"after 3 attempts \(HTTP 429\)"):
        client.fetch(DORA)
    assert not client.cache_path(DORA).exists()


def test_client_errors_are_not_retried(corpus_settings: Settings) -> None:
    requests: list[httpx.Request] = []
    client = make_client(corpus_settings, cellar(requests, httpx.Response(404)), FakeClock())
    with pytest.raises(FetchError, match="HTTP 404"):
        client.fetch(DORA)
    assert len(requests) == 1


def test_redirect_to_another_host_is_refused(corpus_settings: Settings) -> None:
    handler = cellar([], httpx.Response(303, headers={"Location": "https://evil.example/doc"}))
    client = make_client(corpus_settings, handler, FakeClock())
    with pytest.raises(FetchError, match="evil.example"):
        client.fetch(DORA)


def test_redirect_loop_is_cut(corpus_settings: Settings) -> None:
    loop = httpx.Response(303, headers={"Location": CELLAR_DOC})
    client = make_client(corpus_settings, lambda _: loop, FakeClock())
    with pytest.raises(FetchError, match="too many redirects"):
        client.fetch(DORA)
