from typing import Any

import fastembed
import pytest
from tests.test_retrieval_embeddings import StubDense, StubSparse

from vigie.retrieval import models
from vigie.retrieval.embeddings import FastEmbedEmbedder, embedding_id
from vigie.retrieval.models import CustomModel, profile_for, register_custom_model

E5 = "intfloat/multilingual-e5-large"


class RecordingDense(StubDense):
    def __init__(self, model_name: str, cache_dir: str | None = None) -> None:
        super().__init__(model_name, cache_dir)
        self.seen: list[str] = []

    def embed(self, documents: Any) -> Any:
        documents = list(documents)
        self.seen.extend(documents)
        return super().embed(documents)

    def query_embed(self, query: str) -> Any:
        self.seen.append(query)
        return super().query_embed(query)


def test_e5_models_get_their_prefixes_and_others_none() -> None:
    assert profile_for(E5).query_prefix == "query: "
    assert profile_for("intfloat/multilingual-e5-small").passage_prefix == "passage: "
    assert profile_for("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2") == (
        models.DenseProfile()
    )


def test_prefixes_reach_the_dense_model_only() -> None:
    sparse_seen: list[str] = []

    class Sparse(StubSparse):
        def embed(self, documents: Any) -> Any:
            documents = list(documents)
            sparse_seen.extend(documents)
            return super().embed(documents)

    embedder = FastEmbedEmbedder(
        E5, "Qdrant/bm25", "french", dense_factory=RecordingDense, sparse_factory=Sparse
    )
    embedder.embed_documents(["DORA article 28"])
    embedder.embed_query("registre des prestataires")

    dense = embedder._dense
    assert isinstance(dense, RecordingDense)
    assert dense.seen == ["passage: DORA article 28", "query: registre des prestataires"]
    assert sparse_seen == ["DORA article 28"]


def test_the_passage_prefix_moves_the_embedding_id_but_no_prefix_keeps_the_old_one() -> None:
    assert embedding_id("m", "Qdrant/bm25", "french", "") == embedding_id(
        "m", "Qdrant/bm25", "french"
    )
    assert embedding_id("m", "Qdrant/bm25", "french", "passage: ") != embedding_id(
        "m", "Qdrant/bm25", "french"
    )
    embedder = FastEmbedEmbedder(
        E5, "Qdrant/bm25", "french", dense_factory=StubDense, sparse_factory=StubSparse
    )
    assert embedder.embedding_id == embedding_id(E5, "Qdrant/bm25", "french", "passage: ")


def test_custom_models_are_registered_once_and_others_never() -> None:
    calls: list[tuple[str, CustomModel]] = []

    def register(model: str, spec: CustomModel) -> None:
        calls.append((model, spec))

    small = "intfloat/multilingual-e5-small"
    assert register_custom_model(small, known=lambda: [], register=register)
    assert calls == [(small, models.CUSTOM_MODELS[small])]
    assert not register_custom_model(small, known=lambda: [{"model": small}], register=register)
    assert not register_custom_model(E5, known=lambda: [], register=register)
    assert len(calls) == 1


def test_real_registration_hands_fastembed_the_onnx_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    monkeypatch.setattr(
        fastembed.TextEmbedding, "add_custom_model", lambda **kw: captured.update(kw)
    )
    monkeypatch.setattr(fastembed.TextEmbedding, "list_supported_models", lambda: [])

    assert register_custom_model("intfloat/multilingual-e5-base")
    assert captured["model"] == "intfloat/multilingual-e5-base"
    assert captured["sources"].hf == "intfloat/multilingual-e5-base"
    assert (captured["dim"], captured["model_file"]) == (768, "onnx/model.onnx")
    assert captured["normalization"] is True
