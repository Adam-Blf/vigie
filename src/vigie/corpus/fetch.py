"""Polite, cached download of the official XHTML from Cellar.

Cellar answers the CELEX URI with a 303 that points to plain HTTP. We follow redirects by hand
so every hop is upgraded to HTTPS and pinned to the publications office host, instead of
letting the client silently downgrade the transport.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx

from vigie.config import Settings
from vigie.corpus.sources import Regulation, cellar_url

RETRYABLE_STATUS = frozenset({202, 429, 500, 502, 503, 504})


class FetchError(RuntimeError):
    """Cellar could not give us the document, even after the retries."""


class CellarClient:
    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._settings = settings
        self._sleep = sleep
        self._clock = clock
        self._last_request: float | None = None
        self._client = httpx.Client(
            transport=transport,
            timeout=settings.corpus_timeout_s,
            follow_redirects=False,
            headers={"User-Agent": settings.corpus_user_agent},
        )

    def close(self) -> None:
        self._client.close()

    def cache_path(self, regulation: Regulation) -> Path:
        return (
            self._settings.corpus_cache_dir
            / f"{regulation.celex}.{self._settings.corpus_language}.xhtml"
        )

    def fetch(self, regulation: Regulation) -> bytes:
        """Return the XHTML, from the disk cache when we already have it."""
        path = self.cache_path(regulation)
        if path.is_file():
            return path.read_bytes()
        body = self._get_following_redirects(cellar_url(regulation, self._settings))
        path.parent.mkdir(parents=True, exist_ok=True)
        # Write then rename, so an interrupted run never leaves a truncated file that the
        # next run would trust as a cache hit.
        partial = path.with_suffix(".part")
        partial.write_bytes(body)
        partial.replace(path)
        return body

    def _get_following_redirects(self, url: str) -> bytes:
        headers = {
            "Accept": "application/xhtml+xml",
            "Accept-Language": self._settings.corpus_language,
        }
        for _ in range(self._settings.corpus_max_redirects + 1):
            response = self._get_with_retries(self._secure(url), headers)
            if response.is_redirect:
                url = urljoin(url, response.headers["Location"])
                continue
            return response.content
        raise FetchError(f"too many redirects from {url}")

    def _secure(self, url: str) -> str:
        parts = urlsplit(url)
        if parts.hostname != self._settings.cellar_allowed_host:
            raise FetchError(f"refusing to follow a redirect to {parts.hostname!r}")
        return urlunsplit(("https", parts.netloc, parts.path, parts.query, parts.fragment))

    def _get_with_retries(self, url: str, headers: dict[str, str]) -> httpx.Response:
        attempts = self._settings.corpus_max_retries + 1
        last_problem = ""
        for attempt in range(attempts):
            if attempt:
                self._sleep(self._settings.corpus_backoff_s * 2 ** (attempt - 1))
            self._wait_for_slot()
            try:
                response = self._client.get(url, headers=headers)
            except httpx.TransportError as exc:
                last_problem = f"{type(exc).__name__}: {exc}"
                continue
            # A 202 with an empty body is how the EUR-Lex anti-robot wall answers; treat it
            # as transient rather than as a valid, empty document.
            if response.status_code in RETRYABLE_STATUS:
                last_problem = f"HTTP {response.status_code}"
                continue
            if response.is_redirect or response.status_code == 200:
                if response.status_code == 200 and not response.content:
                    last_problem = "empty body"
                    continue
                return response
            raise FetchError(f"HTTP {response.status_code} for {url}")
        raise FetchError(f"gave up on {url} after {attempts} attempts ({last_problem})")

    def _wait_for_slot(self) -> None:
        now = self._clock()
        if self._last_request is not None:
            remaining = self._settings.corpus_min_interval_s - (now - self._last_request)
            if remaining > 0:
                self._sleep(remaining)
                now += remaining
        self._last_request = now
