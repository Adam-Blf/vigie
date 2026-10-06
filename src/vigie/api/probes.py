"""Readiness checks: can this pod reach the vector store and the model right now?

A pod that is alive but cannot answer must leave the load balancer, not serve 503s. The
checks are short HTTP calls with a small timeout, so a slow dependency makes the pod
"not ready" quickly instead of hanging the probe.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx

from vigie.api.bundle import Bundle
from vigie.config import Settings

Probe = Callable[[], bool]


def http_ok(url: str, timeout_s: float, headers: dict[str, str] | None = None) -> bool:
    try:
        response = httpx.get(url, timeout=timeout_s, headers=headers)
    except httpx.HTTPError:
        return False
    return response.status_code == httpx.codes.OK


def llm_probe(settings: Settings, bundle: Bundle) -> Probe:
    provider = bundle.llm.provider
    if provider == "fake":
        return lambda: True
    if provider == "mistral":
        # Probing a paid API on every readiness check would cost money; the key is
        # what decides whether the provider can work at all.
        return lambda: bool(settings.mistral_api_key)
    url = settings.ollama_url.rstrip("/") + "/api/tags"
    return lambda: http_ok(url, settings.readiness_timeout_s)


def retriever_probe(settings: Settings) -> Probe:
    if settings.retriever == "static" or settings.qdrant_url is None:
        # Static passages or an embedded Qdrant live in the process: nothing to reach.
        return lambda: True
    url = settings.qdrant_url.rstrip("/") + "/readyz"
    headers = {"api-key": settings.qdrant_api_key} if settings.qdrant_api_key else None
    return lambda: http_ok(url, settings.readiness_timeout_s, headers)
