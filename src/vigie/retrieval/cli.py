"""`vigie-index`: embed the corpus JSONL files and load them into Qdrant.

Run it after vigie-ingest. It prints the collection name, which is the value to pin in
VIGIE_QDRANT_COLLECTION (and in the release bundle) for a process that has no corpus.
"""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Sequence
from pathlib import Path

from vigie.config import Settings, get_settings
from vigie.corpus.jsonl import read_corpus_dir
from vigie.retrieval.client import QdrantNotConfiguredError, open_client
from vigie.retrieval.embeddings import Embedder, FastEmbedEmbedder
from vigie.retrieval.index import build_index

EXIT_OK = 0
EXIT_FAILED = 1


def build_parser(settings: Settings) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vigie-index", description="Index the Vigie corpus into Qdrant (dense and BM25)."
    )
    parser.add_argument("--corpus", type=Path, default=settings.corpus_dir)
    parser.add_argument(
        "--force", action="store_true", help="re-embed even if the collection is complete"
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    settings: Settings | None = None,
    embedder: Embedder | None = None,
) -> int:
    settings = settings or get_settings()
    args = build_parser(settings).parse_args(argv)
    chunks = read_corpus_dir(args.corpus)
    if not chunks:
        print(f"error: no chunk found in {args.corpus}, run vigie-ingest first", file=sys.stderr)
        return EXIT_FAILED
    try:
        client = open_client(settings)
    except QdrantNotConfiguredError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_FAILED
    started = time.perf_counter()
    try:
        embedder = embedder or FastEmbedEmbedder.from_settings(settings)
        report = build_index(
            client, chunks, embedder, prefix=settings.collection_prefix, force=args.force
        )
        points = client.count(report.collection, exact=True).count
    finally:
        client.close()
    elapsed = time.perf_counter() - started
    print(f"collection   {report.collection}")
    print(f"chunks read  {report.chunks}")
    state = "complete already, nothing embedded" if report.skipped else f"{report.indexed}"
    print(f"embedded     {state}")
    print(f"points       {points}")
    print(f"elapsed      {elapsed:.1f} s")
    return EXIT_OK
