"""Feeds the embeddings of production questions to the J9 drift monitor.

The retriever already embeds every question it searches for. Wrapping its embedder hands
the dense vector to the drift window as well, so drift costs no second inference, and the
monitor never receives a question's text: only the vector crosses over.

Drift is an observer. A missing reference or a vector of the wrong size switches it off
with a warning, and a failure while recording is logged, never raised: no answer is ever
lost because of the drift window.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

import numpy as np

from vigie.config import Settings
from vigie.drift.monitor import DriftMonitor
from vigie.retrieval.embeddings import Embedded, Embedder

log = logging.getLogger("vigie.api.drift")


class DriftTap:
    """An Embedder that also records each query vector in the drift monitor."""

    def __init__(self, inner: Embedder, monitor: DriftMonitor) -> None:
        self._inner = inner
        self._monitor = monitor

    @property
    def embedding_id(self) -> str:
        return self._inner.embedding_id

    @property
    def dense_size(self) -> int:
        return self._inner.dense_size

    def embed_documents(self, texts: Sequence[str]) -> list[Embedded]:
        return self._inner.embed_documents(texts)

    def embed_query(self, text: str) -> Embedded:
        embedded = self._inner.embed_query(text)
        try:
            self._monitor.record(np.asarray([embedded.dense], dtype=np.float64))
        except Exception:
            log.exception("drift: could not record a question embedding")
        return embedded


def load_monitor(settings: Settings) -> DriftMonitor | None:
    """The monitor on the reference files of vigie-drift, or None when they are missing."""
    paths = (settings.drift_reference_path, settings.drift_anchors_path)
    missing = [path.as_posix() for path in paths if not path.is_file()]
    if missing:
        log.warning("drift: reference missing (%s), drift monitoring is off", ", ".join(missing))
        return None
    return DriftMonitor.from_settings(settings)


def tap(embedder: Embedder, monitor: DriftMonitor | None) -> tuple[Embedder, DriftMonitor | None]:
    """Wrap the embedder when the reference was built with vectors of the same size.

    A reference from another embedding model would make every record fail, so the
    mismatch is caught once at start-up instead.
    """
    if monitor is None:
        return embedder, None
    if monitor.reference.dimension != embedder.dense_size:
        log.warning(
            "drift: reference has dimension %d, the embedder %d; drift monitoring is off",
            monitor.reference.dimension,
            embedder.dense_size,
        )
        return embedder, None
    return DriftTap(embedder, monitor), monitor
