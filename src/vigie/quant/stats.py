"""Latency percentiles and file sizes, the two cheap numbers of the study."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class LatencySummary:
    p50_ms: float
    p95_ms: float
    samples: int


def summarize_latency(samples_ms: Sequence[float], warmup: int) -> LatencySummary:
    """p50 and p95 of the samples after dropping the first ``warmup`` ones.

    The first calls pay for lazy allocations inside onnxruntime and for cold caches; they
    describe the start of the process, not the latency a user sees afterwards.
    """
    if warmup < 0:
        raise ValueError("warmup cannot be negative")
    kept = list(samples_ms[warmup:])
    if not kept:
        raise ValueError("no latency sample left after the warm-up")
    p50, p95 = np.percentile(np.asarray(kept, dtype=float), [50, 95])
    return LatencySummary(
        p50_ms=round(float(p50), 3), p95_ms=round(float(p95), 3), samples=len(kept)
    )


def file_size(path: Path) -> int:
    """Bytes on disk of a model, external weight files included when there are any."""
    total = path.stat().st_size
    external = path.with_name(path.name + ".data")
    if external.exists():
        total += external.stat().st_size
    return total
