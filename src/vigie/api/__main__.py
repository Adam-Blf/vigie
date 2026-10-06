"""Run the API: python -m vigie.api

Everything comes from the settings (VIGIE_*): the retriever (Qdrant, or static passages
for a measurement), the LLM provider through the bundle, and the guard chain. Nothing a
request carries can change any of them. The server binds 127.0.0.1 unless VIGIE_HOST says
otherwise, and does not announce itself in a Server header.

When the drift reference exists (vigie-drift build-reference), the retriever's embedder
is wrapped so every searched question also lands, as a vector only, in the drift window.
"""

from __future__ import annotations

import logging
from contextlib import ExitStack

import uvicorn

from vigie.api import redaction
from vigie.api.app import create_app
from vigie.api.drift import load_monitor, tap
from vigie.api.factory import build_state
from vigie.config import get_settings
from vigie.guard.factory import build_input_guard
from vigie.retrieval.embeddings import Embedder, FastEmbedEmbedder
from vigie.retrieval.factory import open_retriever

LOGGERS = ("vigie", "uvicorn", "uvicorn.error", "uvicorn.access", "httpx")


def main() -> int:
    settings = get_settings()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    redaction.install(*LOGGERS)
    drift = load_monitor(settings)
    embedder: Embedder | None = None
    if settings.retriever == "qdrant":
        embedder, drift = tap(FastEmbedEmbedder.from_settings(settings), drift)
    with ExitStack() as stack:
        retriever = stack.enter_context(open_retriever(settings, embedder=embedder))
        guard = build_input_guard(settings)
        state = build_state(settings, input_guard=guard, retriever=retriever, drift=drift)
        uvicorn.run(
            create_app(state),
            host=settings.host,
            port=settings.port,
            server_header=False,
            log_config=None,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
