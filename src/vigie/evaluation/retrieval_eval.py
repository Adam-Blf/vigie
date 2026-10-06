"""Recall@k and MRR of a retriever on one split of the golden set.

Only questions that expect articles take part: an out-of-scope question has nothing to
recall, its success is a refusal, measured elsewhere.

Metrics are computed on distinct articles. Several paragraphs of one article are one hit,
so the retriever is asked for `depth` passages, more than k, to leave room for k distinct
articles after deduplication.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass

from vigie.evaluation.golden import GoldenQuestion, Split
from vigie.evaluation.metrics import mean, recall_at_k, reciprocal_rank
from vigie.rag.pipeline import Retriever


@dataclass(frozen=True)
class RetrievalRow:
    id: str
    expected: tuple[str, ...]
    retrieved: tuple[str, ...]
    recall_at_k: float
    reciprocal_rank: float


@dataclass(frozen=True)
class RetrievalResult:
    split: Split
    k: int
    depth: int
    questions: int
    recall_at_k: float
    mrr: float
    rows: tuple[RetrievalRow, ...]

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def evaluate_retrieval(
    questions: Sequence[GoldenQuestion],
    retriever: Retriever,
    *,
    split: Split,
    k: int,
    depth: int,
) -> RetrievalResult:
    if depth < k:
        raise ValueError("depth must be at least k, or recall@k could never reach 1")
    rows: list[RetrievalRow] = []
    for question in questions:
        if question.split != split or not question.expected_articles:
            continue
        passages = retriever.search(question.question, depth)
        retrieved = tuple(dict.fromkeys(p.article_id for p in passages))
        rows.append(
            RetrievalRow(
                id=question.id,
                expected=question.expected_articles,
                retrieved=retrieved,
                recall_at_k=recall_at_k(retrieved, question.expected_articles, k),
                reciprocal_rank=reciprocal_rank(retrieved, question.expected_articles),
            )
        )
    if not rows:
        raise ValueError(f"no question of the {split} split expects an article")
    return RetrievalResult(
        split=split,
        k=k,
        depth=depth,
        questions=len(rows),
        recall_at_k=mean([r.recall_at_k for r in rows]),
        mrr=mean([r.reciprocal_rank for r in rows]),
        rows=tuple(rows),
    )
