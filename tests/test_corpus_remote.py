import httpx
import pytest

from vigie.config import Settings
from vigie.corpus.models import Chunk
from vigie.corpus.remote import RemoteCorpusError, fetch_published_corpus

URL = "https://github.com/example/vigie/releases/download/v0.1.0/corpus.jsonl"
CHUNK = Chunk(
    regulation="DORA",
    celex="32022R2554",
    kind="article",
    article="64",
    paragraph=None,
    title="Entrée en vigueur et application",
    chapter="CHAPITRE IX - Dispositions finales",
    text="Il s’applique à partir du 17 janvier 2025.",
    url="https://eur-lex.europa.eu/legal-content/FR/TXT/?uri=CELEX:32022R2554#art_64",
    eid="art_64",
    retrieved_on="2026-10-02",
)


def fetch(settings: Settings, response: httpx.Response, url: str = URL) -> list[Chunk]:
    transport = httpx.MockTransport(lambda _: response)
    return fetch_published_corpus(url, settings, transport=transport)


def test_published_jsonl_is_read_back_into_chunks() -> None:
    body = CHUNK.model_dump_json() + "\n\n"
    assert fetch(Settings(_env_file=None), httpx.Response(200, text=body)) == [CHUNK]


def test_plain_http_url_is_refused() -> None:
    with pytest.raises(RemoteCorpusError, match="HTTPS"):
        fetch(Settings(_env_file=None), httpx.Response(200), URL.replace("https", "http"))


def test_redirect_down_to_http_is_refused() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.scheme == "https":
            return httpx.Response(302, headers={"Location": "http://objects.example/corpus"})
        return httpx.Response(200, text="")

    transport = httpx.MockTransport(handler)
    with pytest.raises(RemoteCorpusError, match="objects.example"):
        fetch_published_corpus(URL, Settings(_env_file=None), transport=transport)


def test_http_error_status_is_reported() -> None:
    with pytest.raises(RemoteCorpusError, match="HTTP 404"):
        fetch(Settings(_env_file=None), httpx.Response(404))


def test_unreachable_host_is_reported() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    with pytest.raises(RemoteCorpusError, match="ConnectError"):
        fetch_published_corpus(
            URL, Settings(_env_file=None), transport=httpx.MockTransport(handler)
        )


def test_malformed_line_is_reported() -> None:
    with pytest.raises(RemoteCorpusError, match="invalid corpus line"):
        fetch(Settings(_env_file=None), httpx.Response(200, text='{"regulation": "DORA"}'))
