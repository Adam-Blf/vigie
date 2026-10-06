"""Load every model the API image carries and run one inference on each.

    python -m vigie.deploy.models

The image build runs it twice. In the models stage, with network, loading the embedders
is what downloads them into VIGIE_EMBEDDING_CACHE_DIR. In the final stage it runs again
as the non-root user with no network at all: anything still missing fails the build
there, rather than the first question in production.

The model names come from the settings, never from the Dockerfile, so a new default
embedding model in config.py is the one baked into the next image.
"""

from __future__ import annotations

import sys
import time
from collections.abc import Callable, Sequence
from typing import TextIO

from vigie.config import Settings, get_settings
from vigie.guard.base import InputGuard
from vigie.guard.factory import build_input_guard
from vigie.retrieval.embeddings import Embedder, FastEmbedEmbedder

PROBE = "Qui porte la responsabilité ultime du risque lié aux TIC selon DORA ?"

EmbedderFactory = Callable[[Settings], Embedder]
GuardFactory = Callable[[Settings], InputGuard]


def check_models(
    settings: Settings,
    out: TextIO,
    embedder_factory: EmbedderFactory = FastEmbedEmbedder.from_settings,
    guard_factory: GuardFactory = build_input_guard,
) -> None:
    started = time.perf_counter()
    embedder = embedder_factory(settings)
    query = embedder.embed_query(PROBE)
    out.write(f"embedding  {embedder.embedding_id} dense={len(query.dense)}")
    out.write(f" sparse_terms={len(query.sparse.indices)}\n")
    decision = guard_factory(settings).check(PROBE)
    out.write(f"guard      classifier={settings.guard_classifier} blocked={decision.blocked}\n")
    out.write(f"elapsed    {time.perf_counter() - started:.1f} s\n")


def main(argv: Sequence[str] | None = None, out: TextIO = sys.stdout) -> int:
    del argv  # no options: what to load is entirely in the settings
    check_models(get_settings(), out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
