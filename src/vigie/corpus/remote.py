"""Fallback when Cellar is down: read the corpus JSONL published with a release."""

from __future__ import annotations

from urllib.parse import urlsplit

import httpx

from vigie.config import Settings
from vigie.corpus.jsonl import parse_chunks
from vigie.corpus.models import Chunk
from vigie.corpus.render import normalize


class RemoteCorpusError(RuntimeError):
    """The published corpus could not be fetched or read."""


def fetch_published_corpus(
    url: str, settings: Settings, *, transport: httpx.BaseTransport | None = None
) -> list[Chunk]:
    if urlsplit(url).scheme != "https":
        raise RemoteCorpusError("the published corpus is only fetched over HTTPS")
    with httpx.Client(
        transport=transport,
        timeout=settings.corpus_timeout_s,
        follow_redirects=True,
        headers={"User-Agent": settings.corpus_user_agent},
    ) as client:
        try:
            response = client.get(url)
        except httpx.HTTPError as exc:
            raise RemoteCorpusError(f"cannot reach {url}: {type(exc).__name__}") from exc
    # Release assets redirect to a storage host; a hop back to plain HTTP would undo the
    # point of asking for HTTPS in the first place.
    if response.url.scheme != "https":
        raise RemoteCorpusError(f"redirected to a non HTTPS location: {response.url.host}")
    if response.status_code != 200:
        raise RemoteCorpusError(f"HTTP {response.status_code} for {url}")
    try:
        return parse_chunks(response.text)
    except ValueError as exc:
        raise RemoteCorpusError(f"invalid corpus line: {normalize(str(exc))[:200]}") from exc
