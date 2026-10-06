"""Shared helpers for the drift tests: a deterministic embedder and the question sets."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np

from vigie.drift.embedder import Matrix, normalize_rows
from vigie.drift.monitor import DriftThresholds

FIXTURE = Path(__file__).parent / "fixtures" / "drift_questions.json"
_TOKEN = re.compile(r"[^\W\d_]{5,}")


class HashingEmbedder:
    """Bag of hashed words: same text, same vector, on every machine.

    Short words are skipped so that articles and pronouns, shared by every French
    sentence, do not pull cooking questions toward the regulations. sha256 replaces
    ``hash()`` because Python salts the latter per process.
    """

    def __init__(self, dimension: int = 512) -> None:
        self.dimension = dimension
        self.calls = 0

    def embed(self, texts: Sequence[str]) -> Matrix:
        self.calls += 1
        rows = np.zeros((len(texts), self.dimension))
        for row, text in enumerate(texts):
            for token in _TOKEN.findall(text.lower()):
                digest = hashlib.sha256(token.encode()).digest()
                rows[row, int.from_bytes(digest[:4], "big") % self.dimension] += 1.0
        return normalize_rows(rows)


def load_questions() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return data


def thresholds(**overrides: float) -> DriftThresholds:
    values: dict[str, Any] = {
        "centroid_distance": 0.3,
        "out_of_scope_similarity": 0.3,
        "out_of_scope_ratio": 0.25,
        "ks_alpha": 0.01,
        "min_window": 10,
    }
    values.update(overrides)
    return DriftThresholds(**values)


def cluster(center: int, count: int, dimension: int = 16, seed: int = 0) -> Matrix:
    """Unit vectors scattered around one basis axis, for synthetic scenarios."""
    rng = np.random.default_rng(seed)
    points = rng.normal(scale=0.15, size=(count, dimension))
    points[:, center] += 1.0
    return normalize_rows(points)
