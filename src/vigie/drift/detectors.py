"""The three drift indicators, as pure functions over numpy arrays.

Each one catches a different failure. The centroid distance sees the whole stream
moving to another topic. The out-of-scope ratio sees a share of users asking about
things the corpus does not cover, even when the average barely moves. The KS test
sees the similarity distribution changing shape, which tends to show up before the
other two cross their thresholds.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from vigie.drift.embedder import Matrix

# Terms of the Kolmogorov series. The terms decay as exp(-2 j^2 lambda^2), so for any
# statistic large enough to matter the sum has converged long before this.
_KS_SERIES_TERMS = 100


def centroid_cosine_distance(reference_centroid: Matrix, window: Matrix) -> float:
    """Cosine distance, between 0 and 2, from the reference centroid to the window's."""
    if window.shape[0] == 0:
        raise ValueError("the window is empty")
    current = window.mean(axis=0)
    denominator = float(np.linalg.norm(reference_centroid) * np.linalg.norm(current))
    if denominator == 0.0:
        # Vectors that cancel out carry no direction: report the maximal orthogonal
        # distance instead of dividing by zero.
        return 1.0
    return 1.0 - float(reference_centroid @ current) / denominator


def max_similarity(vectors: Matrix, anchors: Matrix) -> Matrix:
    """For each unit vector, its cosine similarity to the closest anchor."""
    similarities: Matrix = (vectors @ anchors.T).max(axis=1)
    return similarities


def out_of_scope_ratio(similarities: Matrix, threshold: float) -> float:
    """Share of questions whose best match in the corpus stays below ``threshold``."""
    if similarities.size == 0:
        raise ValueError("no similarity to score")
    return float(np.mean(similarities < threshold))


@dataclass(frozen=True)
class KSResult:
    statistic: float
    pvalue: float


def _kolmogorov_survival(lam: float) -> float:
    """P(K > lam) for the Kolmogorov distribution, as an alternating series."""
    if lam < 0.2:
        # Below 0.2 the alternating series needs many terms to settle, while the true
        # value is 1 to within 1e-12, so the shortcut is exact for any decision.
        return 1.0
    j = np.arange(1, _KS_SERIES_TERMS + 1)
    terms = (-1.0) ** (j - 1) * np.exp(-2.0 * j**2 * lam**2)
    return float(min(1.0, max(0.0, 2.0 * terms.sum())))


def ks_two_sample(sample_a: Matrix, sample_b: Matrix) -> KSResult:
    """Two-sample Kolmogorov-Smirnov test, two-sided, asymptotic p-value.

    Written with numpy rather than scipy to keep scipy out of the API image. The
    p-value uses the effective-size correction from Stephens (1970), which stays
    accurate down to the 30-question windows the monitor works with.
    """
    a = np.sort(np.asarray(sample_a, dtype=np.float64).ravel())
    b = np.sort(np.asarray(sample_b, dtype=np.float64).ravel())
    if a.size == 0 or b.size == 0:
        raise ValueError("both samples must be non-empty")
    pooled = np.concatenate([a, b])
    cdf_a = np.searchsorted(a, pooled, side="right") / a.size
    cdf_b = np.searchsorted(b, pooled, side="right") / b.size
    statistic = float(np.max(np.abs(cdf_a - cdf_b)))
    effective = float(np.sqrt(a.size * b.size / (a.size + b.size)))
    lam = (effective + 0.12 + 0.11 / effective) * statistic
    return KSResult(statistic=statistic, pvalue=_kolmogorov_survival(lam))
