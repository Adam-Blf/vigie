"""Dev-split diagnostics behind the RRF setting: each branch alone, then fusion variants.

Run from the repository root with the same settings as vigie-index, for example:
VIGIE_QDRANT_PATH=.qdrant PYTHONPATH=src python docs/proofs/J2/iterations_dev.py
It reads the dev split only; the sealed test split is never looked at.
"""

from collections.abc import Callable, Sequence

from qdrant_client import models

from vigie.config import Settings
from vigie.evaluation.golden import load_golden
from vigie.evaluation.metrics import mean, recall_at_k, reciprocal_rank
from vigie.retrieval.client import open_client
from vigie.retrieval.embeddings import Embedded, FastEmbedEmbedder
from vigie.retrieval.factory import resolve_collection

settings = Settings()
embedder = FastEmbedEmbedder.from_settings(settings)
client = open_client(settings)
name = resolve_collection(settings, embedder)
questions = [
    q for q in load_golden(settings.golden_path) if q.split == "dev" and q.expected_articles
]
queries = {q.id: embedder.embed_query(q.question) for q in questions}


def articles(points: Sequence[models.ScoredPoint]) -> list[str]:
    ids = (f"{p.payload['regulation']}:{p.payload['article']}" for p in points if p.payload)
    return list(dict.fromkeys(ids))


def sparse(query: Embedded) -> models.SparseVector:
    return models.SparseVector(indices=list(query.sparse.indices), values=list(query.sparse.values))


def report(label: str, search: Callable[[Embedded], list[models.ScoredPoint]]) -> None:
    recalls: list[float] = []
    ranks: list[float] = []
    for q in questions:
        found = articles(search(queries[q.id]))
        recalls.append(recall_at_k(found, q.expected_articles, 5))
        ranks.append(reciprocal_rank(found, q.expected_articles))
    print(f"{label:<28} recall@5={mean(recalls):.4f} mrr={mean(ranks):.4f}")


def branches(query: Embedded, limit: int) -> list[models.Prefetch]:
    return [
        models.Prefetch(query=list(query.dense), using="dense", limit=limit),
        models.Prefetch(query=sparse(query), using="bm25", limit=limit),
    ]


def fused(fusion: models.FusionQuery | models.RrfQuery, limit: int) -> Callable[..., list]:
    def run(query: Embedded) -> list[models.ScoredPoint]:
        return client.query_points(
            name, prefetch=branches(query, limit), query=fusion, limit=20
        ).points

    return run


report(
    "dense only",
    lambda e: client.query_points(name, query=list(e.dense), using="dense", limit=20).points,
)
report(
    "bm25 only",
    lambda e: client.query_points(name, query=sparse(e), using="bm25", limit=20).points,
)
for limit in (10, 20, 50, 100):
    report(
        f"hybrid rrf prefetch={limit}", fused(models.FusionQuery(fusion=models.Fusion.RRF), limit)
    )
for k, weights in (
    (2, [2.0, 1.0]),
    (2, [3.0, 1.0]),
    (10, [1.0, 1.0]),
    (60, [1.0, 1.0]),
    (60, [2.0, 1.0]),
):
    report(
        f"rrf k={k} w={weights}", fused(models.RrfQuery(rrf=models.Rrf(k=k, weights=weights)), 20)
    )
client.close()
