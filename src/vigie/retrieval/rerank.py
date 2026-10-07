"""Second pass over the fused candidates with a cross-encoder.

The dense and BM25 branches each score a question and a passage separately, then compare
two summaries. A cross-encoder reads both together, which is slower but much better at
telling "the article that answers" from "an article on the same topic". It only ever
sees the few dozen passages the fusion already kept, so the cost stays bounded.

The model outputs a logit. The passage score becomes its sigmoid, a number in (0, 1): the
RAG pipeline drops passages under VIGIE_RAG_MIN_SCORE (0 by default), and a raw negative
logit would make it refuse questions the reranker merely found less relevant than others.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Protocol

from vigie.rag.types import Passage

# Characters of body text the cross-encoder reads per passage, about 300 words. A chunk
# can reach 1200 words; reading all of it multiplied the cost by four for each of the
# thirty candidates (12 GB of RAM on the first try), and the opening of an article, where
# its subject is stated, is what decides its relevance.
RERANK_MAX_CHARS = 1500


class Reranker(Protocol):
    @property
    def model(self) -> str: ...

    def scores(self, query: str, documents: Sequence[str]) -> list[float]: ...


class _CrossEncoder(Protocol):
    def rerank(self, query: str, documents: Iterable[str]) -> Iterable[float]: ...


CrossEncoderFactory = Callable[[str, "str | None"], _CrossEncoder]


def _fastembed_cross_encoder(model: str, cache_dir: str | None) -> _CrossEncoder:
    from fastembed.rerank.cross_encoder import TextCrossEncoder

    encoder: _CrossEncoder = TextCrossEncoder(model_name=model, cache_dir=cache_dir)
    return encoder


class FastEmbedReranker:
    def __init__(
        self,
        model: str,
        cache_dir: Path | None = None,
        *,
        factory: CrossEncoderFactory = _fastembed_cross_encoder,
    ) -> None:
        self._model = model
        self._encoder = factory(model, str(cache_dir) if cache_dir else None)

    @property
    def model(self) -> str:
        return self._model

    def scores(self, query: str, documents: Sequence[str]) -> list[float]:
        return [float(s) for s in self._encoder.rerank(query, documents)]


def sigmoid(logit: float) -> float:
    # Split on the sign so a very negative logit cannot overflow exp().
    if logit >= 0:
        return 1.0 / (1.0 + math.exp(-logit))
    z = math.exp(logit)
    return z / (1.0 + z)


def passage_text(passage: Passage) -> str:
    """Same header as the indexed text, so the reranker also sees "DORA article 28"."""
    return f"{passage.regulation} article {passage.article} {passage.title}\n{passage.text}"


def rerank(
    reranker: Reranker, question: str, passages: Sequence[Passage], top_k: int
) -> list[Passage]:
    """Reorder by cross-encoder score, keep top_k, ties left in their fused order."""
    if not passages:
        return []
    logits = reranker.scores(question, [passage_text(p) for p in passages])
    order = sorted(range(len(passages)), key=lambda i: -logits[i])
    return [replace(passages[i], score=sigmoid(logits[i])) for i in order[:top_k]]
