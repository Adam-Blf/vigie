"""Turn questions into unit vectors.

Drift detection only needs vectors, so everything downstream of this file works on
numpy arrays and never sees a question's text. Tests swap the real model for a
deterministic fake through the ``Embedder`` protocol.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Protocol

import numpy as np
import numpy.typing as npt

if TYPE_CHECKING:
    from fastembed import TextEmbedding

Matrix = npt.NDArray[np.float64]


class Embedder(Protocol):
    """Anything that maps a batch of texts to one row vector per text."""

    def embed(self, texts: Sequence[str]) -> Matrix: ...


def normalize_rows(vectors: npt.ArrayLike) -> Matrix:
    """Scale every row to unit length so a dot product is a cosine similarity.

    A zero row stays at zero rather than turning into NaN: it then has a similarity of
    0 to everything, which is the honest answer for an empty embedding.
    """
    matrix = np.atleast_2d(np.asarray(vectors, dtype=np.float64))
    if matrix.ndim != 2:
        raise ValueError(f"expected a 2D matrix of embeddings, got shape {matrix.shape}")
    if not np.all(np.isfinite(matrix)):
        raise ValueError("embeddings contain NaN or infinite values")
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return np.divide(matrix, norms, out=np.zeros_like(matrix), where=norms > 0)


class FastEmbedEmbedder:
    """Adapter over fastembed, the same ONNX runtime the retrieval index uses.

    The model is loaded on first use: building the monitor at API start-up must not
    cost a model download when drift is never queried.
    """

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._model: TextEmbedding | None = None

    def embed(self, texts: Sequence[str]) -> Matrix:
        if not texts:
            raise ValueError("cannot embed an empty batch")
        if self._model is None:
            from fastembed import TextEmbedding

            self._model = TextEmbedding(self.model_name)
        return normalize_rows(np.stack(list(self._model.embed(list(texts)))))
