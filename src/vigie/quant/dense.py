"""A plain cosine search over the corpus chunks, enough to compare two embedding variants.

It is not the production retriever (that one is hybrid, in Qdrant). Both variants go
through the very same search, so whatever this search lacks cancels out in the comparison
and only the effect of quantization is left.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from vigie.corpus.models import Chunk
from vigie.evaluation.golden import GoldenQuestion
from vigie.evaluation.metrics import mean_recall_at_k, mean_reciprocal_rank
from vigie.evaluation.regulations import article_id

FloatArray = NDArray[np.float32]


def mean_pool(token_embeddings: FloatArray, attention_mask: NDArray[np.int64]) -> FloatArray:
    """Average the token vectors, padding excluded, as the model's pooling config asks."""
    mask = attention_mask[..., None].astype(np.float32)
    summed = (token_embeddings * mask).sum(axis=1)
    counts = np.clip(mask.sum(axis=1), 1e-9, None)
    pooled: FloatArray = (summed / counts).astype(np.float32)
    return pooled


def l2_normalize(vectors: FloatArray) -> FloatArray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    normalized: FloatArray = (vectors / np.clip(norms, 1e-12, None)).astype(np.float32)
    return normalized


def chunk_text(chunk: Chunk) -> str:
    # The article title carries the topic in a few words; prefixing it helps the 128 token
    # window of the model, which cuts the end of long articles anyway.
    return f"{chunk.title}\n{chunk.text}" if chunk.title else chunk.text


def chunk_article_ids(chunks: Sequence[Chunk]) -> list[str]:
    return [article_id(chunk.regulation, chunk.article) for chunk in chunks]


def rank_chunks(query: FloatArray, documents: FloatArray, limit: int) -> list[int]:
    """Indices of the ``limit`` most similar documents, best first.

    Vectors are normalized beforehand, so the dot product is the cosine similarity.
    """
    scores = documents @ query
    order = np.argsort(-scores, kind="stable")
    return [int(i) for i in order[:limit]]


def ranked_articles(
    query: FloatArray, documents: FloatArray, article_ids: Sequence[str], depth: int
) -> list[str]:
    """Distinct article ids in rank order, from the ``depth`` best chunks.

    Several chunks of one article must count once, otherwise a long article split in four
    would fill the top five on its own.
    """
    seen: dict[str, None] = {}
    for index in rank_chunks(query, documents, depth):
        seen.setdefault(article_ids[index], None)
    return list(seen)


@dataclass(frozen=True)
class RetrievalScore:
    recall_at_k: float
    mrr: float
    questions: int


def retrieval_questions(questions: Sequence[GoldenQuestion]) -> list[GoldenQuestion]:
    """Dev questions that expect at least one article; the test split never gets here."""
    return [q for q in questions if q.split == "dev" and q.expected_articles]


def score_retrieval(
    rankings: Sequence[Sequence[str]], questions: Sequence[GoldenQuestion], k: int
) -> RetrievalScore:
    if len(rankings) != len(questions):
        raise ValueError("one ranking per question is required")
    if any(q.split != "dev" for q in questions):
        raise ValueError("the quantization decision is taken on the dev split only")
    runs = [(list(r), q.expected_articles) for r, q in zip(rankings, questions, strict=True)]
    return RetrievalScore(
        recall_at_k=mean_recall_at_k(runs, k),
        mrr=mean_reciprocal_rank(runs),
        questions=len(questions),
    )
