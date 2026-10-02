import sys
import types
from collections.abc import Iterable, Iterator

import numpy as np
import pytest

from vigie.drift.embedder import FastEmbedEmbedder, normalize_rows


def test_normalize_rows_returns_unit_vectors() -> None:
    matrix = normalize_rows([[3.0, 4.0], [0.0, 2.0]])
    assert np.linalg.norm(matrix, axis=1) == pytest.approx([1.0, 1.0])
    assert matrix[0] == pytest.approx([0.6, 0.8])


def test_normalize_rows_promotes_a_single_vector() -> None:
    assert normalize_rows([1.0, 0.0]).shape == (1, 2)


def test_normalize_rows_leaves_a_zero_row_at_zero() -> None:
    matrix = normalize_rows([[0.0, 0.0], [1.0, 1.0]])
    assert matrix[0] == pytest.approx([0.0, 0.0])
    assert not np.isnan(matrix).any()


def test_normalize_rows_rejects_wrong_shapes_and_bad_values() -> None:
    with pytest.raises(ValueError, match="2D"):
        normalize_rows(np.zeros((2, 2, 2)))
    with pytest.raises(ValueError, match="NaN"):
        normalize_rows([[np.nan, 1.0]])


class _FakeTextEmbedding:
    instances = 0

    def __init__(self, model_name: str) -> None:
        type(self).instances += 1
        self.model_name = model_name

    def embed(self, texts: Iterable[str]) -> Iterator[np.ndarray]:
        for text in texts:
            yield np.array([float(len(text)), 1.0])


def test_fastembed_adapter_loads_the_model_once_and_normalizes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A stand-in module skips importing onnxruntime, which alone costs half a minute.
    fake_module = types.ModuleType("fastembed")
    fake_module.TextEmbedding = _FakeTextEmbedding  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "fastembed", fake_module)
    _FakeTextEmbedding.instances = 0
    embedder = FastEmbedEmbedder("some/model")
    assert _FakeTextEmbedding.instances == 0

    first = embedder.embed(["abc", "a"])
    embedder.embed(["again"])

    assert _FakeTextEmbedding.instances == 1
    assert first.shape == (2, 2)
    assert np.linalg.norm(first, axis=1) == pytest.approx([1.0, 1.0])


def test_fastembed_adapter_refuses_an_empty_batch() -> None:
    with pytest.raises(ValueError, match="empty batch"):
        FastEmbedEmbedder("some/model").embed([])
