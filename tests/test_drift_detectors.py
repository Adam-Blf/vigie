import numpy as np
import pytest

from vigie.drift.detectors import (
    _kolmogorov_survival,
    centroid_cosine_distance,
    ks_two_sample,
    max_similarity,
    out_of_scope_ratio,
)

AXES = np.eye(3)


def test_centroid_distance_is_zero_for_the_same_direction() -> None:
    window = np.array([[1.0, 0.0, 0.0], [1.0, 0.0, 0.0]])
    assert centroid_cosine_distance(AXES[0], window) == pytest.approx(0.0)


def test_centroid_distance_spans_orthogonal_and_opposite() -> None:
    assert centroid_cosine_distance(AXES[0], AXES[1:2]) == pytest.approx(1.0)
    assert centroid_cosine_distance(AXES[0], -AXES[0:1]) == pytest.approx(2.0)


def test_centroid_distance_of_a_cancelling_window_is_one() -> None:
    window = np.array([[1.0, 0.0, 0.0], [-1.0, 0.0, 0.0]])
    assert centroid_cosine_distance(AXES[0], window) == 1.0


def test_centroid_distance_rejects_an_empty_window() -> None:
    with pytest.raises(ValueError, match="empty"):
        centroid_cosine_distance(AXES[0], np.empty((0, 3)))


def test_max_similarity_keeps_the_closest_anchor() -> None:
    vectors = np.array([[1.0, 0.0, 0.0], [0.6, 0.8, 0.0], [0.0, 0.0, 1.0]])
    anchors = AXES[:2]
    assert max_similarity(vectors, anchors) == pytest.approx([1.0, 0.8, 0.0])


def test_out_of_scope_ratio_counts_values_strictly_below_threshold() -> None:
    similarities = np.array([0.1, 0.3, 0.5, 0.9])
    assert out_of_scope_ratio(similarities, 0.3) == pytest.approx(0.25)
    assert out_of_scope_ratio(similarities, 0.95) == pytest.approx(1.0)


def test_out_of_scope_ratio_rejects_nothing_to_score() -> None:
    with pytest.raises(ValueError, match="no similarity"):
        out_of_scope_ratio(np.array([]), 0.3)


def test_kolmogorov_survival_matches_the_textbook_critical_values() -> None:
    # 1.358 and 1.628 are the classic 5 % and 1 % critical values of the distribution.
    assert _kolmogorov_survival(1.358) == pytest.approx(0.05, abs=5e-4)
    assert _kolmogorov_survival(1.628) == pytest.approx(0.01, abs=5e-4)
    assert _kolmogorov_survival(0.1) == 1.0
    assert _kolmogorov_survival(10.0) == pytest.approx(0.0, abs=1e-12)


def test_ks_on_identical_samples_finds_nothing() -> None:
    sample = np.linspace(0.0, 1.0, 50)
    result = ks_two_sample(sample, sample.copy())
    assert result.statistic == 0.0
    assert result.pvalue == 1.0


def test_ks_on_disjoint_samples_is_conclusive() -> None:
    result = ks_two_sample(np.linspace(0.5, 0.9, 40), np.linspace(-0.2, 0.2, 30))
    assert result.statistic == 1.0
    assert result.pvalue < 1e-6


def test_ks_keeps_two_draws_of_one_distribution_apart_from_a_shift() -> None:
    rng = np.random.default_rng(7)
    same = ks_two_sample(rng.normal(size=200), rng.normal(size=200))
    shifted = ks_two_sample(rng.normal(size=200), rng.normal(loc=1.0, size=200))
    assert same.pvalue > 0.05
    assert shifted.pvalue < 1e-6


def test_ks_statistic_on_a_hand_computed_case() -> None:
    # Empirical CDFs differ most at 2: two thirds of a are <= 2, none of b.
    result = ks_two_sample(np.array([1.0, 2.0, 3.0]), np.array([2.5, 3.5]))
    assert result.statistic == pytest.approx(2 / 3)


def test_ks_rejects_an_empty_sample() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        ks_two_sample(np.array([]), np.array([1.0]))
