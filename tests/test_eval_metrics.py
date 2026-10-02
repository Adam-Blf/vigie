from collections.abc import Sequence

import pytest

from vigie.evaluation.metrics import (
    CitationCase,
    bootstrap_ci,
    citation_coverage,
    citation_precision,
    correct_refusal_rate,
    invented_citations,
    mean,
    mean_recall_at_k,
    mean_reciprocal_rank,
    raw_citation_validity,
    recall_at_k,
    reciprocal_rank,
)


def test_recall_at_k_counts_distinct_articles_in_the_cutoff() -> None:
    retrieved = ["DORA:5", "DORA:5", "DORA:28", "DORA:30", "DORA:6"]
    assert recall_at_k(retrieved, {"DORA:28", "DORA:30"}, k=2) == 0.5
    assert recall_at_k(retrieved, {"DORA:28", "DORA:30"}, k=3) == 1.0
    assert recall_at_k([], {"DORA:28"}, k=5) == 0.0


@pytest.mark.parametrize(("k", "expected"), [(0, {"DORA:28"}), (5, set())])
def test_recall_rejects_bad_input(k: int, expected: set[str]) -> None:
    with pytest.raises(ValueError):
        recall_at_k(["DORA:28"], expected, k=k)


def test_reciprocal_rank_uses_first_relevant_after_dedupe() -> None:
    assert reciprocal_rank(["A:1", "A:1", "A:2"], {"A:2"}) == 0.5
    assert reciprocal_rank(["A:1"], {"A:2"}) == 0.0
    with pytest.raises(ValueError):
        reciprocal_rank(["A:1"], set())


def test_means_over_runs() -> None:
    runs = [(["A:1", "A:2"], {"A:2"}), (["A:3"], {"A:9"})]
    assert mean_reciprocal_rank(runs) == 0.25
    assert mean_recall_at_k(runs, k=5) == 0.5
    with pytest.raises(ValueError):
        mean([])


def test_correct_refusal_rate_ignores_in_scope_rows() -> None:
    outcomes = [(True, True), (True, False), (False, True), (True, True)]
    assert correct_refusal_rate(outcomes) == pytest.approx(2 / 3)
    with pytest.raises(ValueError):
        correct_refusal_rate([(False, False)])


def case(cited: Sequence[str], allowed: set[str], expected: set[str]) -> CitationCase:
    return CitationCase(tuple(cited), frozenset(allowed), frozenset(expected))


def test_raw_validity_counts_invented_citations() -> None:
    cases = [
        case(["A:1", "A:1", "A:7"], {"A:1", "A:2"}, {"A:1"}),
        case(["A:2"], {"A:2"}, {"A:3"}),
    ]
    assert raw_citation_validity(cases) == pytest.approx(2 / 3)
    assert raw_citation_validity([case([], {"A:1"}, {"A:1"})]) == 1.0


def test_invented_citations_counts_distinct_leaks_per_answer() -> None:
    cases = [
        case(["A:1", "A:7", "A:7", "A:8"], {"A:1"}, {"A:1"}),
        case(["A:7"], {"A:2"}, {"A:2"}),
    ]
    assert invented_citations(cases) == 3


def test_invented_citations_is_zero_for_clean_or_silent_answers() -> None:
    assert invented_citations([case(["A:1", "A:1"], {"A:1"}, {"A:1"})]) == 0
    assert invented_citations([case([], {"A:1"}, {"A:1"})]) == 0
    assert invented_citations([]) == 0


def test_precision_and_coverage_are_micro_averaged() -> None:
    cases = [
        case(["A:1", "A:2"], {"A:1", "A:2"}, {"A:1", "A:3"}),
        case(["A:4"], {"A:4"}, {"A:4"}),
    ]
    assert citation_precision(cases) == pytest.approx(2 / 3)
    assert citation_coverage(cases) == pytest.approx(2 / 3)


def test_silent_assistant_fails_precision_and_coverage() -> None:
    cases = [case([], {"A:1"}, {"A:1"})]
    assert citation_precision(cases) == 0.0
    assert citation_coverage(cases) == 0.0
    with pytest.raises(ValueError):
        citation_coverage([case(["A:1"], {"A:1"}, set())])


def test_bootstrap_is_seeded_and_brackets_the_point() -> None:
    values = [0.0, 1.0, 1.0, 0.0, 1.0, 1.0, 1.0, 0.0, 1.0, 1.0]
    first = bootstrap_ci(values, mean, draws=1000, seed=7)
    assert first == bootstrap_ci(values, mean, draws=1000, seed=7)
    assert first.point == 0.7
    assert first.low <= first.point <= first.high
    assert 0.0 <= first.low < first.high <= 1.0
    wider = bootstrap_ci(values, mean, draws=1000, seed=7, confidence=0.99)
    assert wider.low <= first.low and wider.high >= first.high


def test_bootstrap_of_a_constant_has_zero_width() -> None:
    interval = bootstrap_ci([1.0, 1.0, 1.0], mean, draws=50, seed=1)
    assert (interval.low, interval.point, interval.high) == (1.0, 1.0, 1.0)


@pytest.mark.parametrize(
    ("items", "draws", "confidence"),
    [([], 10, 0.95), ([1.0], 0, 0.95), ([1.0], 10, 1.0), ([1.0], 10, 0.0)],
)
def test_bootstrap_rejects_bad_arguments(items: list[float], draws: int, confidence: float) -> None:
    with pytest.raises(ValueError):
        bootstrap_ci(items, mean, draws=draws, seed=0, confidence=confidence)
