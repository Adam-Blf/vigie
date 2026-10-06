"""One place that turns the settings into a Qdrant client.

A server URL wins over a local path. The local path is Qdrant's embedded mode, a folder
on disk with no server to run, which is enough for a laptop demo and for the proofs;
":memory:" keeps everything in RAM for the tests.
"""

from __future__ import annotations

from qdrant_client import QdrantClient

from vigie.config import Settings

MEMORY = ":memory:"


class QdrantNotConfiguredError(RuntimeError):
    """Neither a server URL nor a local path was given."""


def open_client(settings: Settings) -> QdrantClient:
    if settings.qdrant_url:
        return QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
    if settings.qdrant_path == MEMORY:
        return QdrantClient(location=MEMORY)
    if settings.qdrant_path:
        return QdrantClient(path=settings.qdrant_path)
    raise QdrantNotConfiguredError(
        "set VIGIE_QDRANT_URL (server) or VIGIE_QDRANT_PATH (local folder or :memory:)"
    )
