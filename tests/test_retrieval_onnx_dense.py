from collections.abc import Sequence
from pathlib import Path

import fastembed
import numpy as np
import pytest
from tests.test_retrieval_embeddings import StubSparse

from vigie.config import Settings
from vigie.quant import encoder as encoder_module
from vigie.retrieval.embeddings import FastEmbedEmbedder, embedding_id
from vigie.retrieval.onnx_dense import (
    OnnxDense,
    OnnxModelMissingError,
    load_int8,
    model_dir,
    model_slug,
)

MODEL = "intfloat/multilingual-e5-small"


class FakeEncoder:
    """Three dimensions: text length, a constant, the batch position."""

    def __init__(self) -> None:
        self.batches: list[list[str]] = []

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        self.batches.append(list(texts))
        return np.array([[len(t), 1.0, i] for i, t in enumerate(texts)], dtype=np.float32)


def export(quant_dir: Path, model: str = MODEL) -> Path:
    folder = model_dir(quant_dir, model)
    folder.mkdir(parents=True)
    (folder / "model-int8.onnx").write_bytes(b"onnx")
    (folder / "tokenizer.json").write_text("{}", encoding="utf-8")
    return folder


def test_one_folder_per_model() -> None:
    assert model_slug(MODEL) == "intfloat-multilingual-e5-small"
    assert model_dir(Path("data/quant"), MODEL) == Path("data/quant/intfloat-multilingual-e5-small")


def test_documents_go_in_one_batch_and_a_query_alone() -> None:
    encoder = FakeEncoder()
    dense = OnnxDense(encoder, 3)
    assert dense.embedding_size == 3
    rows = list(dense.embed(["ab", "abcd"]))
    assert [r.tolist() for r in rows] == [[2.0, 1.0, 0.0], [4.0, 1.0, 1.0]]
    assert list(dense.embed([])) == []
    assert next(dense.query_embed("abc")).tolist() == [3.0, 1.0, 0.0]
    assert encoder.batches == [["ab", "abcd"], ["abc"]]


def test_a_missing_export_says_how_to_make_it(tmp_path: Path) -> None:
    with pytest.raises(OnnxModelMissingError, match="vigie-quant export --models"):
        load_int8(MODEL, tmp_path, 512)


def test_the_export_is_opened_with_the_token_window(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = export(tmp_path)
    opened: list[tuple[Path, Path, int]] = []

    def from_files(model: Path, tokenizer: Path, max_tokens: int) -> FakeEncoder:
        opened.append((model, tokenizer, max_tokens))
        return FakeEncoder()

    monkeypatch.setattr(encoder_module.OnnxEncoder, "from_files", staticmethod(from_files))
    dense = load_int8(MODEL, tmp_path, 512)
    assert opened == [(folder / "model-int8.onnx", folder / "tokenizer.json", 512)]
    assert dense.embedding_size == 3


def test_settings_with_int8_load_the_export_and_name_a_new_collection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    export(tmp_path)
    encoder = FakeEncoder()
    monkeypatch.setattr(encoder_module.OnnxEncoder, "from_files", staticmethod(lambda *a: encoder))
    monkeypatch.setattr(fastembed, "SparseTextEmbedding", StubSparse)
    settings = Settings(_env_file=None, dense_model=MODEL, dense_variant="int8", quant_dir=tmp_path)

    embedder = FastEmbedEmbedder.from_settings(settings)

    assert isinstance(embedder._dense, OnnxDense)
    assert embedder.embedding_id.startswith("multilingual-e5-small-int8-")
    assert embedder.embedding_id == embedding_id(
        MODEL, "Qdrant/bm25", "french", "passage: ", "int8", settings.dense_max_tokens
    )
    other_window = embedding_id(MODEL, "Qdrant/bm25", "french", "passage: ", "int8", 512)
    assert settings.dense_max_tokens != 512 and embedder.embedding_id != other_window
    assert embedder.embedding_id != embedding_id(MODEL, "Qdrant/bm25", "french", "passage: ")
    embedder.embed_query("registre")
    assert encoder.batches[-1] == ["query: registre"]
