"""Dense and BM25 vectors for chunks and questions.

The index and the search only talk to the Embedder protocol, so the unit tests run on a
tiny deterministic embedder and never download a model. FastEmbedEmbedder is the real one:
fastembed runs on onnxruntime, without torch, which keeps the API image inside its memory
budget (brief, section 11.7).
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from vigie.config import Settings


@dataclass(frozen=True)
class SparseVector:
    indices: tuple[int, ...]
    values: tuple[float, ...]


@dataclass(frozen=True)
class Embedded:
    dense: tuple[float, ...]
    sparse: SparseVector


class Embedder(Protocol):
    @property
    def embedding_id(self) -> str: ...

    @property
    def dense_size(self) -> int: ...

    def embed_documents(self, texts: Sequence[str]) -> list[Embedded]: ...

    def embed_query(self, text: str) -> Embedded: ...


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def embedding_id(dense_model: str, sparse_model: str, language: str) -> str:
    """Readable model name plus a short hash of the whole embedding setup.

    The dense name alone would not do: switching BM25 to English changes every sparse
    vector without changing a single dense dimension, and Qdrant would happily mix both.
    """
    setup = f"{dense_model}|{sparse_model}|{language}".encode()
    return f"{_slug(dense_model.rsplit('/', 1)[-1])}-{hashlib.sha256(setup).hexdigest()[:6]}"


# What fastembed hands back, reduced to the members used here.
class _DenseModel(Protocol):
    @property
    def embedding_size(self) -> int: ...

    def embed(self, documents: Iterable[str]) -> Iterable[Any]: ...

    def query_embed(self, query: str) -> Iterable[Any]: ...


class _SparseModel(Protocol):
    def embed(self, documents: Iterable[str]) -> Iterable[Any]: ...

    def query_embed(self, query: str) -> Iterable[Any]: ...


DenseFactory = Callable[[str, "str | None"], _DenseModel]
SparseFactory = Callable[[str, "str | None", str], _SparseModel]


def _fastembed_dense(model: str, cache_dir: str | None) -> _DenseModel:
    from fastembed import TextEmbedding

    dense: _DenseModel = TextEmbedding(model_name=model, cache_dir=cache_dir)
    return dense


def _fastembed_sparse(model: str, cache_dir: str | None, language: str) -> _SparseModel:
    from fastembed import SparseTextEmbedding

    sparse: _SparseModel = SparseTextEmbedding(
        model_name=model, cache_dir=cache_dir, language=language
    )
    return sparse


def _to_sparse(raw: Any) -> SparseVector:
    return SparseVector(
        indices=tuple(int(i) for i in raw.indices),
        values=tuple(float(v) for v in raw.values),
    )


def _to_dense(raw: Any) -> tuple[float, ...]:
    return tuple(float(v) for v in raw)


class FastEmbedEmbedder:
    def __init__(
        self,
        dense_model: str,
        sparse_model: str,
        language: str,
        cache_dir: Path | None = None,
        *,
        dense_factory: DenseFactory = _fastembed_dense,
        sparse_factory: SparseFactory = _fastembed_sparse,
    ) -> None:
        cache = str(cache_dir) if cache_dir else None
        self._id = embedding_id(dense_model, sparse_model, language)
        self._dense = dense_factory(dense_model, cache)
        self._sparse = sparse_factory(sparse_model, cache, language)

    @classmethod
    def from_settings(cls, settings: Settings) -> FastEmbedEmbedder:
        return cls(
            settings.dense_model,
            settings.sparse_model,
            settings.sparse_language,
            settings.embedding_cache_dir,
        )

    @property
    def embedding_id(self) -> str:
        return self._id

    @property
    def dense_size(self) -> int:
        return self._dense.embedding_size

    def embed_documents(self, texts: Sequence[str]) -> list[Embedded]:
        dense = [_to_dense(v) for v in self._dense.embed(texts)]
        sparse = [_to_sparse(v) for v in self._sparse.embed(texts)]
        return [Embedded(d, s) for d, s in zip(dense, sparse, strict=True)]

    def embed_query(self, text: str) -> Embedded:
        # BM25 weighs a query differently from a document (no length normalisation, each
        # term counted once), which is why fastembed has a separate query_embed.
        dense = _to_dense(next(iter(self._dense.query_embed(text))))
        sparse = _to_sparse(next(iter(self._sparse.query_embed(text))))
        return Embedded(dense, sparse)
