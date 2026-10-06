"""Run the API: python -m vigie.api

Everything comes from the settings (VIGIE_*): the retriever (Qdrant, or static passages
for a measurement), the LLM provider through the bundle, and the guard chain. Nothing a
request carries can change any of them. The server binds 127.0.0.1 unless VIGIE_HOST says
otherwise, and does not announce itself in a Server header.
"""

from __future__ import annotations

import logging
from contextlib import ExitStack

import uvicorn

from vigie.api import redaction
from vigie.api.app import create_app
from vigie.api.factory import build_state
from vigie.config import get_settings
from vigie.guard.factory import build_input_guard
from vigie.retrieval.factory import open_retriever

LOGGERS = ("vigie", "uvicorn", "uvicorn.error", "uvicorn.access", "httpx")


def main() -> int:
    settings = get_settings()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    redaction.install(*LOGGERS)
    with ExitStack() as stack:
        retriever = stack.enter_context(open_retriever(settings))
        state = build_state(settings, input_guard=build_input_guard(settings), retriever=retriever)
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
