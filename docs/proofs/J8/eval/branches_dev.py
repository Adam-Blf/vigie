"""Dev-split diagnostics for one embedding setup: each branch alone, then fusion variants.

Run from the repository root with the settings of the collection to inspect, for example
VIGIE_DENSE_MODEL=intfloat/multilingual-e5-large VIGIE_DENSE_VARIANT=fp32
VIGIE_QDRANT_PATH=data/cache/qdrant PYTHONPATH=src python docs/proofs/J8/eval/branches_dev.py
Only the dev split is read; the sealed test split is never looked at.
"""

from collections.abc import Callable, Sequence

from qdrant_client import models

from vigie.config import Settings
from vigie.evaluation.golden import load_golden
from vigie.evaluation.metrics import mean, recall_at_k, reciprocal_rank
from vigie.retrieval.client import open_client
from vigie.retrieval.embeddings import Embedded, FastEmbedEmbedder
from vigie.retrieval.factory import resolve_collection
from vigie.retrieval.language import is_english

settings = Settings()
embedder = FastEmbedEmbedder.from_settings(settings)
client = open_client(settings)
name = resolve_collection(settings, embedder)
questions = [
    q for q in load_golden(settings.golden_path) if q.split == "dev" and q.expected_articles
]
queries = {q.id: embedder.embed_query(q.question) for q in questions}
english = {q.id for q in questions if is_english(q.question)}
print(f"collection {name}, {len(questions)} dev questions")


def articles(points: Sequence[models.ScoredPoint]) -> list[str]:
    ids = (f"{p.payload['regulation']}:{p.payload['article']}" for p in points if p.payload)
    return list(dict.fromkeys(ids))


def sparse(query: Embedded) -> models.SparseVector:
    return models.SparseVector(indices=list(query.sparse.indices), values=list(query.sparse.values))


Search = Callable[[Embedded], list[models.ScoredPoint]]


def report(label: str, search: Search, on_english: Search | None = None) -> None:
    recalls: list[float] = []
    ranks: list[float] = []
    for q in questions:
        chosen = on_english if on_english and q.id in english else search
        found = articles(chosen(queries[q.id]))
        recalls.append(recall_at_k(found, q.expected_articles, 5))
        ranks.append(reciprocal_rank(found, q.expected_articles))
    print(f"{label:<28} recall@5={mean(recalls):.4f} mrr={mean(ranks):.4f}")


def fused(fusion: models.RrfQuery, limit: int) -> Callable[[Embedded], list[models.ScoredPoint]]:
    def run(query: Embedded) -> list[models.ScoredPoint]:
        prefetch = [
            models.Prefetch(query=list(query.dense), using="dense", limit=limit),
            models.Prefetch(query=sparse(query), using="bm25", limit=limit),
        ]
        return client.query_points(name, prefetch=prefetch, query=fusion, limit=20).points

    return run


def dense(e: Embedded) -> list[models.ScoredPoint]:
    return client.query_points(name, query=list(e.dense), using="dense", limit=20).points


report("dense only", dense)
report(
    "bm25 only",
    lambda e: client.query_points(name, query=sparse(e), using="bm25", limit=20).points,
)
for k, weights, limit in (
    (60, [1.0, 1.0], 20),
    (60, [2.0, 1.0], 20),
    (60, [3.0, 1.0], 20),
    (60, [1.0, 1.0], 50),
):
    report(
        f"rrf k={k} w={weights} p={limit}",
        fused(models.RrfQuery(rrf=models.Rrf(k=k, weights=weights)), limit),
    )
    # Same fusion on French questions, dense alone on English ones.
    report(
        "  + dense only if english",
        fused(models.RrfQuery(rrf=models.Rrf(k=k, weights=weights)), limit),
        dense,
    )
client.close()
