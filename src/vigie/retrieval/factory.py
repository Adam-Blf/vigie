"""Pick the retriever the settings ask for, and close what it opened.

Callers (the RAG command line today, the API next) only see the pipeline's Retriever
protocol: search(question, top_k) -> list[Passage]. Switching from the fixed passages of
the LLM measurements to real Qdrant retrieval is a setting, VIGIE_RETRIEVER.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from vigie.config import Settings
from vigie.corpus.jsonl import read_corpus_dir
from vigie.rag.pipeline import Retriever
from vigie.rag.static_retriever import StaticRetriever
from vigie.retrieval.client import open_client
from vigie.retrieval.embeddings import Embedder, FastEmbedEmbedder
from vigie.retrieval.index import collection_name
from vigie.retrieval.rerank import FastEmbedReranker, Reranker
from vigie.retrieval.search import QdrantRetriever


class RetrieverConfigError(RuntimeError):
    """The settings do not say enough to build the requested retriever."""


def resolve_collection(settings: Settings, embedder: Embedder) -> str:
    """The pinned name when there is one, otherwise the name vigie-index gives the corpus."""
    if settings.qdrant_collection:
        return settings.qdrant_collection
    chunks = read_corpus_dir(settings.corpus_dir)
    if not chunks:
        raise RetrieverConfigError(
            f"no chunk in {settings.corpus_dir} to derive the collection name from; "
            "run vigie-ingest or set VIGIE_QDRANT_COLLECTION"
        )
    return collection_name(settings.collection_prefix, embedder.embedding_id, chunks)


@contextmanager
def open_retriever(
    settings: Settings,
    *,
    passages: Path | None = None,
    embedder: Embedder | None = None,
    reranker: Reranker | None = None,
) -> Iterator[Retriever]:
    """Yield a ready retriever; `passages` forces the static one on that file.

    `embedder` and `reranker` replace the models the settings name, for the tests and for
    an evaluation run that already holds them in memory.
    """
    if passages is not None or settings.retriever == "static":
        path = passages or settings.static_passages_path
        if path is None:
            raise RetrieverConfigError("the static retriever needs VIGIE_STATIC_PASSAGES_PATH")
        yield StaticRetriever.from_json(path)
        return
    embedder = embedder or FastEmbedEmbedder.from_settings(settings)
    if reranker is None and settings.rerank_model:
        reranker = FastEmbedReranker(settings.rerank_model, settings.embedding_cache_dir)
    client = open_client(settings)
    try:
        yield QdrantRetriever(
            client,
            resolve_collection(settings, embedder),
            embedder,
            prefetch_limit=settings.retrieval_prefetch_limit,
            rrf_k=settings.retrieval_rrf_k or None,
            reranker=reranker,
            rerank_depth=settings.rerank_depth,
            pin_references=settings.retrieval_pin_references,
            dense_weight=settings.retrieval_dense_weight,
            sparse_on_english=settings.retrieval_sparse_on_english,
        )
    finally:
        # Local mode holds a lock on its folder until closed; a second process would fail.
        client.close()
