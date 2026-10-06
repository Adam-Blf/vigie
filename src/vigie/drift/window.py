"""Sliding window over the embeddings of recent production questions.

Only vectors enter the window. The question text is dropped by the caller before
anything reaches this class, so the drift state holds nothing a person could read
back, and the audit log stays the single place where text lives, with its own
retention.
"""

from __future__ import annotations

from collections import deque

import numpy as np

from vigie.drift.embedder import Matrix, normalize_rows


class EmbeddingWindow:
    """Bounded first-in first-out buffer: memory stays flat whatever the traffic."""

    def __init__(self, max_size: int, dimension: int) -> None:
        if max_size < 1:
            raise ValueError("the window must hold at least one embedding")
        if dimension < 1:
            raise ValueError("the embedding dimension must be positive")
        self.max_size = max_size
        self.dimension = dimension
        self._rows: deque[Matrix] = deque(maxlen=max_size)

    def __len__(self) -> int:
        return len(self._rows)

    def add(self, embeddings: Matrix) -> int:
        """Append one vector or a batch and return how many rows came in.

        The oldest rows fall out once ``max_size`` is reached.
        """
        matrix = normalize_rows(embeddings)
        if matrix.shape[1] != self.dimension:
            raise ValueError(
                f"expected embeddings of dimension {self.dimension}, got {matrix.shape[1]}"
            )
        self._rows.extend(matrix)
        return int(matrix.shape[0])

    def matrix(self) -> Matrix:
        if not self._rows:
            return np.empty((0, self.dimension), dtype=np.float64)
        return np.stack(self._rows)
