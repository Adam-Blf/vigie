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
from vigie.retrieval.models import profile_for, register_custom_model
from vigie.retrieval.onnx_dense import load_int8


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


def embedding_id(
    dense_model: str,
    sparse_model: str,
    language: str,
    passage_prefix: str = "",
    variant: str = "fp32",
    window: int | None = None,
) -> str:
    """Readable model name plus a short hash of the whole embedding setup.

    The dense name alone would not do: switching BM25 to English changes every sparse
    vector without changing a single dense dimension, and Qdrant would happily mix both.
    The passage prefix changes every stored vector too; it only enters the hash when set,
    so the collections built before prefixes existed keep their names. The int8 variant
    gives other vectors again, and says so in the readable part too. So does the token
    window of the ONNX export: a passage cut at 128 tokens is not the one cut at 512.
    """
    parts = [dense_model, sparse_model, language] + ([passage_prefix] if passage_prefix else [])
    name = _slug(dense_model.rsplit("/", 1)[-1])
    if variant != "fp32":
        parts.append(variant)
        name = f"{name}-{variant}"
    if window is not None:
        parts.append(f"window={window}")
    setup = "|".join(parts).encode()
    return f"{name}-{hashlib.sha256(setup).hexdigest()[:6]}"


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

    register_custom_model(model)
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
        variant: str = "fp32",
        window: int | None = None,
    ) -> None:
        cache = str(cache_dir) if cache_dir else None
        profile = profile_for(dense_model)
        self._query_prefix = profile.query_prefix
        self._passage_prefix = profile.passage_prefix
        self._id = embedding_id(
            dense_model, sparse_model, language, self._passage_prefix, variant, window
        )
        self._dense = dense_factory(dense_model, cache)
        self._sparse = sparse_factory(sparse_model, cache, language)

    @classmethod
    def from_settings(cls, settings: Settings) -> FastEmbedEmbedder:
        """fp32 is fastembed's copy of the model; int8 is the J12 export (onnx_dense.py)."""
        if settings.dense_variant == "int8":

            def int8(model: str, _cache: str | None) -> _DenseModel:
                return load_int8(model, settings.quant_dir, settings.dense_max_tokens)

            return cls(
                settings.dense_model,
                settings.sparse_model,
                settings.sparse_language,
                settings.embedding_cache_dir,
                dense_factory=int8,
                variant="int8",
                window=settings.dense_max_tokens,
            )
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
        # The prefix is for the dense model only: BM25 would count "passage" as a word.
        prefixed = [self._passage_prefix + t for t in texts]
        dense = [_to_dense(v) for v in self._dense.embed(prefixed)]
        sparse = [_to_sparse(v) for v in self._sparse.embed(texts)]
        return [Embedded(d, s) for d, s in zip(dense, sparse, strict=True)]

    def embed_query(self, text: str) -> Embedded:
        # BM25 weighs a query differently from a document (no length normalisation, each
        # term counted once), which is why fastembed has a separate query_embed.
        dense = _to_dense(next(iter(self._dense.query_embed(self._query_prefix + text))))
        sparse = _to_sparse(next(iter(self._sparse.query_embed(text))))
        return Embedded(dense, sparse)
