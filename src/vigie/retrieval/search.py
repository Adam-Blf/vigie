"""Hybrid search: dense and BM25 candidates fused by reciprocal rank in Qdrant.

Dense vectors catch paraphrases ("who is ultimately accountable" for "responsabilité
ultime"), BM25 catches the exact words a regulation uses and references such as
"article 28". RRF merges the two rankings without having to calibrate their scores against
each other, which cosine and BM25 scores never are.

The score of a fused passage is its RRF score, the sum over both lists of 1/(k + position),
positions counted from 0: it says how high the passage ranked, not how similar it is. With
k = 60, a passage first in both lists scores 2/60.

Without k (VIGIE_RETRIEVAL_RRF_K=0) the query is the plain FusionQuery(fusion=RRF), whose
constant is fixed at 2 and lets the first hit of a single list outweigh broad agreement; on
the dev split it gave recall@5 0.57 against 0.64 for k = 60 (docs/proofs/J2/).

Two optional steps follow the fusion. A cross-encoder can rerank the first candidates
(rerank.py), and the chunks of an article the question names explicitly ("article 28
DORA", references.py) are put first, ahead of whatever the models preferred.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from typing import Any

from qdrant_client import QdrantClient, models

from vigie.rag.types import Passage
from vigie.retrieval.embeddings import Embedder
from vigie.retrieval.index import DENSE, SPARSE
from vigie.retrieval.references import ArticleRef, parse_references
from vigie.retrieval.rerank import Reranker, rerank

# Chunks kept per named article. A long article split in many chunks would otherwise fill
# the whole context and push out the neighbouring articles the answer often needs too.
PINNED_PER_REFERENCE = 3


class CollectionMissingError(RuntimeError):
    """The collection the settings point at has not been built."""


def _regulation_filter(regulations: Sequence[str] | None) -> models.Filter | None:
    if not regulations:
        return None
    condition = models.FieldCondition(
        key="regulation", match=models.MatchAny(any=[r.upper() for r in regulations])
    )
    return models.Filter(must=[condition])


def _key(passage: Passage) -> tuple[str, str]:
    return passage.regulation, passage.eid


def _paragraph_key(passage: Passage) -> tuple[int, str]:
    paragraph = passage.paragraph or ""
    return (int(paragraph), "") if paragraph.isdigit() else (10_000, paragraph)


def pin_references(
    ranked: Sequence[Passage], named: Sequence[Sequence[Passage]], top_k: int
) -> list[Passage]:
    """Named articles first, then the ranked list without the passages already moved up.

    Inside an article, the chunks the search had already found keep their order and come
    first; the others follow in paragraph order. A pinned chunk takes the best score of the
    list, so the score floor of the pipeline can never drop what the user asked for.
    """
    best = ranked[0].score if ranked else 1.0
    position = {_key(p): i for i, p in enumerate(ranked)}
    pinned: list[Passage] = []
    for chunks in named:
        found = sorted(
            (c for c in chunks if _key(c) in position),
            key=lambda c: position[_key(c)],
        )
        rest = sorted((c for c in chunks if _key(c) not in position), key=_paragraph_key)
        pinned.extend(replace(c, score=best) for c in (found + rest)[:PINNED_PER_REFERENCE])
    moved = {_key(p) for p in pinned}
    tail = [p for p in ranked if _key(p) not in moved]
    return (pinned + tail)[:top_k]


def _passage(payload: dict[str, Any], score: float) -> Passage:
    return Passage(
        regulation=payload["regulation"],
        article=payload["article"],
        paragraph=payload["paragraph"],
        title=payload["title"],
        text=payload["text"],
        url=payload["url"],
        eid=payload["eid"],
        score=score,
    )


class QdrantRetriever:
    """Fits the RAG pipeline's Retriever protocol, plus an optional regulation filter."""

    def __init__(
        self,
        client: QdrantClient,
        collection: str,
        embedder: Embedder,
        *,
        prefetch_limit: int,
        rrf_k: int | None = None,
        reranker: Reranker | None = None,
        rerank_depth: int = 0,
        pin_references: bool = False,
    ) -> None:
        if not client.collection_exists(collection):
            raise CollectionMissingError(f"collection {collection} not found, run vigie-index")
        self._client = client
        self._collection = collection
        self._embedder = embedder
        self._prefetch_limit = prefetch_limit
        self._reranker = reranker
        self._rerank_depth = rerank_depth
        self._pin = pin_references
        self._fusion: models.FusionQuery | models.RrfQuery = (
            models.FusionQuery(fusion=models.Fusion.RRF)
            if rrf_k is None
            else models.RrfQuery(rrf=models.Rrf(k=rrf_k))
        )

    @property
    def collection(self) -> str:
        return self._collection

    def search(
        self, question: str, top_k: int, regulations: Sequence[str] | None = None
    ) -> list[Passage]:
        query = self._embedder.embed_query(question)
        sparse = models.SparseVector(
            indices=list(query.sparse.indices), values=list(query.sparse.values)
        )
        # The filter goes into each branch: filtering after the fusion would let the other
        # regulations eat the candidate budget and leave fewer than top_k passages.
        where = _regulation_filter(regulations)
        limit = max(self._prefetch_limit, top_k)
        # The reranker needs a wider pool than top_k to have something to reorder.
        pool = max(top_k, self._rerank_depth) if self._reranker else top_k
        response = self._client.query_points(
            self._collection,
            prefetch=[
                models.Prefetch(query=list(query.dense), using=DENSE, limit=limit, filter=where),
                models.Prefetch(query=sparse, using=SPARSE, limit=limit, filter=where),
            ],
            query=self._fusion,
            limit=pool,
            with_payload=True,
        )
        ranked = [_passage(point.payload or {}, point.score) for point in response.points]
        if self._reranker:
            ranked = rerank(self._reranker, question, ranked, top_k)
        refs = parse_references(question) if self._pin else []
        if regulations:
            allowed = {r.upper() for r in regulations}
            refs = [r for r in refs if r.regulation in allowed]
        if not refs:
            return ranked[:top_k]
        return pin_references(ranked, [self._article_chunks(r) for r in refs], top_k)

    def _article_chunks(self, ref: ArticleRef) -> list[Passage]:
        where = models.Filter(
            must=[
                models.FieldCondition(
                    key="regulation", match=models.MatchValue(value=ref.regulation)
                ),
                models.FieldCondition(key="article", match=models.MatchValue(value=ref.article)),
            ]
        )
        points, _ = self._client.scroll(
            self._collection, scroll_filter=where, limit=100, with_payload=True
        )
        return [_passage(point.payload or {}, 0.0) for point in points]
