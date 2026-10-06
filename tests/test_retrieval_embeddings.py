from collections.abc import Iterable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import fastembed
import numpy as np
import pytest

from vigie.config import Settings
from vigie.retrieval.embeddings import FastEmbedEmbedder, SparseVector, embedding_id

DENSE = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


class StubDense:
    """Stands in for fastembed.TextEmbedding: numpy rows, like the real one."""

    def __init__(self, model_name: str, cache_dir: str | None = None) -> None:
        self.model_name = model_name
        self.cache_dir = cache_dir

    @property
    def embedding_size(self) -> int:
        return 3

    def embed(self, documents: Iterable[str]) -> Iterable[Any]:
        return (np.array([len(d), 1.0, 0.0], dtype=np.float32) for d in documents)

    def query_embed(self, query: str) -> Iterable[Any]:
        return iter([np.array([0.0, 0.0, len(query)], dtype=np.float32)])


class StubSparse:
    def __init__(self, model_name: str, cache_dir: str | None = None, language: str = "") -> None:
        self.model_name = model_name
        self.cache_dir = cache_dir
        self.language = language

    def embed(self, documents: Iterable[str]) -> Iterable[Any]:
        for d in documents:
            yield SimpleNamespace(indices=np.array([7, 9]), values=np.array([1.0, len(d)]))

    def query_embed(self, query: str) -> Iterable[Any]:
        yield SimpleNamespace(indices=np.array([7]), values=np.array([1.0]))


def test_embedding_id_is_readable_and_stable() -> None:
    first = embedding_id(DENSE, "Qdrant/bm25", "french")
    assert first == embedding_id(DENSE, "Qdrant/bm25", "french")
    assert first.startswith("paraphrase-multilingual-minilm-l12-v2-")
    assert len(first.rsplit("-", 1)[1]) == 6


@pytest.mark.parametrize(
    ("dense", "sparse", "language"),
    [
        ("other/model", "Qdrant/bm25", "french"),
        (DENSE, "Qdrant/bm42", "french"),
        (DENSE, "Qdrant/bm25", "english"),
    ],
)
def test_embedding_id_moves_with_any_part_of_the_setup(
    dense: str, sparse: str, language: str
) -> None:
    assert embedding_id(dense, sparse, language) != embedding_id(DENSE, "Qdrant/bm25", "french")


def test_vectors_are_converted_to_plain_python() -> None:
    embedder = FastEmbedEmbedder(
        DENSE, "Qdrant/bm25", "french", dense_factory=StubDense, sparse_factory=StubSparse
    )
    assert embedder.dense_size == 3
    assert embedder.embedding_id == embedding_id(DENSE, "Qdrant/bm25", "french")

    docs = embedder.embed_documents(["abc", "abcdef"])
    assert [d.dense for d in docs] == [(3.0, 1.0, 0.0), (6.0, 1.0, 0.0)]
    assert docs[1].sparse == SparseVector((7, 9), (1.0, 6.0))
    assert all(type(v) is float for v in docs[0].dense)
    assert all(type(i) is int for i in docs[0].sparse.indices)

    query = embedder.embed_query("abcd")
    assert query.dense == (0.0, 0.0, 4.0)
    assert query.sparse == SparseVector((7,), (1.0,))


def test_from_settings_passes_models_language_and_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The default factories import fastembed lazily; patching its classes proves they hand
    # over the configured names without downloading anything.
    monkeypatch.setattr(fastembed, "TextEmbedding", StubDense)
    monkeypatch.setattr(fastembed, "SparseTextEmbedding", StubSparse)
    settings = Settings(_env_file=None, embedding_cache_dir=tmp_path, sparse_language="english")

    embedder = FastEmbedEmbedder.from_settings(settings)

    dense, sparse = embedder._dense, embedder._sparse
    assert isinstance(dense, StubDense) and isinstance(sparse, StubSparse)
    assert dense.model_name == settings.dense_model
    assert dense.cache_dir == str(tmp_path)
    assert (sparse.model_name, sparse.language) == ("Qdrant/bm25", "english")


def test_no_cache_dir_lets_fastembed_choose(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fastembed, "TextEmbedding", StubDense)
    monkeypatch.setattr(fastembed, "SparseTextEmbedding", StubSparse)
    embedder = FastEmbedEmbedder.from_settings(Settings(_env_file=None))
    assert isinstance(embedder._dense, StubDense)
    assert embedder._dense.cache_dir is None
