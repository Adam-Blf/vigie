"""Hybrid search: dense and BM25 candidates fused by reciprocal rank in Qdrant.

Dense vectors catch paraphrases ("who is ultimately accountable" for "responsabilité
ultime"), BM25 catches the exact words a regulation uses and references such as
"article 28". RRF merges the two rankings without having to calibrate their scores against
each other, which cosine and BM25 scores never are.

The score of a fused passage is its RRF score, the sum of 1/(rank + 1) over both lists
with Qdrant's default constant: 1.0 for a passage first in both, 0.5 for first in one list
only. It says how high the passage ranked, not how similar it is.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from qdrant_client import QdrantClient, models

from vigie.rag.types import Passage
from vigie.retrieval.embeddings import Embedder
from vigie.retrieval.index import DENSE, SPARSE


class CollectionMissingError(RuntimeError):
    """The collection the settings point at has not been built."""


def _regulation_filter(regulations: Sequence[str] | None) -> models.Filter | None:
    if not regulations:
        return None
    condition = models.FieldCondition(
        key="regulation", match=models.MatchAny(any=[r.upper() for r in regulations])
    )
    return models.Filter(must=[condition])


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
    ) -> None:
        if not client.collection_exists(collection):
            raise CollectionMissingError(f"collection {collection} not found, run vigie-index")
        self._client = client
        self._collection = collection
        self._embedder = embedder
        self._prefetch_limit = prefetch_limit

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
        response = self._client.query_points(
            self._collection,
            prefetch=[
                models.Prefetch(query=list(query.dense), using=DENSE, limit=limit, filter=where),
                models.Prefetch(query=sparse, using=SPARSE, limit=limit, filter=where),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=top_k,
            with_payload=True,
        )
        return [_passage(point.payload or {}, point.score) for point in response.points]
