"""Measure one embedding variant: size, per-query latency, recall@k and MRR on dev.

The corpus is encoded once per variant. Latency is then taken query by query, one text
at a time, because that is what the API does for each incoming question; batch throughput
would flatter both variants and say nothing about the p95 a user waits for.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from vigie.corpus.jsonl import read_chunks
from vigie.corpus.models import Chunk
from vigie.evaluation.golden import GoldenQuestion
from vigie.quant.decision import VariantResult
from vigie.quant.dense import (
    FloatArray,
    chunk_article_ids,
    chunk_text,
    ranked_articles,
    score_retrieval,
)
from vigie.quant.stats import summarize_latency
from vigie.rag.labels import eurlex_url
from vigie.rag.types import Passage

# Chunks read per query to build the article ranking. Deep enough for MRR to see a
# relevant article ranked well below the top five, cheap enough to stay negligible.
RANK_DEPTH = 50


class Encoder(Protocol):
    def encode(self, texts: Sequence[str]) -> FloatArray: ...


def load_chunks(corpus_dir: Path) -> list[Chunk]:
    files = sorted(corpus_dir.glob("*.jsonl"))
    if not files:
        raise FileNotFoundError(f"no chunk JSONL in {corpus_dir}, run vigie-ingest first")
    return [chunk for path in files for chunk in read_chunks(path)]


@dataclass(frozen=True)
class StudySettings:
    k: int
    warmup: int
    passes: int


def measure_variant(
    name: str,
    encoder: Encoder,
    size_bytes: int,
    chunks: Sequence[Chunk],
    questions: Sequence[GoldenQuestion],
    settings: StudySettings,
    clock: Callable[[], float] = time.perf_counter,
) -> VariantResult:
    documents = encoder.encode([chunk_text(c) for c in chunks])
    article_ids = chunk_article_ids(chunks)
    timings: list[float] = []
    rankings: list[list[str]] = []
    for run in range(settings.passes):
        for question in questions:
            start = clock()
            vector = encoder.encode([question.question])[0]
            timings.append((clock() - start) * 1000.0)
            if run == 0:
                rankings.append(ranked_articles(vector, documents, article_ids, RANK_DEPTH))
    latency = summarize_latency(timings, settings.warmup)
    score = score_retrieval(rankings, questions, settings.k)
    return VariantResult(
        name=name,
        size_bytes=size_bytes,
        recall_at_k=score.recall_at_k,
        mrr=score.mrr,
        latency_p50_ms=latency.p50_ms,
        latency_p95_ms=latency.p95_ms,
        questions=score.questions,
    )


def to_passage(chunk: Chunk, score: float) -> Passage:
    return Passage(
        regulation=chunk.regulation,
        article=chunk.article,
        paragraph=chunk.paragraph,
        title=chunk.title,
        text=chunk.text,
        url=chunk.url or eurlex_url(chunk.regulation),
        eid=chunk.eid,
        score=score,
    )


def top_passages(
    query: FloatArray, documents: FloatArray, chunks: Sequence[Chunk], top_k: int
) -> list[Passage]:
    """The ``top_k`` best chunks as RAG passages, for the LLM part of the study."""
    scores = documents @ query
    order = sorted(range(len(chunks)), key=lambda i: -float(scores[i]))[:top_k]
    return [to_passage(chunks[i], float(scores[i])) for i in order]
