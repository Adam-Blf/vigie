"""Deterministic evaluation metrics: no model call, same input gives the same number.

They run in CI as the regression gate, so every edge case has an explicit answer instead
of a NaN that would make a threshold comparison silently false.

Article identifiers are compared as plain strings (``DORA:28``); deduplication happens
here so a passage retrieved twice, or a citation repeated in an answer, counts once.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass
from typing import TypeVar

import numpy as np

T = TypeVar("T")


def _dedupe(items: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(items))


def recall_at_k(retrieved: Sequence[str], expected: Collection[str], k: int) -> float:
    """Share of the expected articles found in the first ``k`` distinct retrieved ones."""
    if k < 1:
        raise ValueError("k must be at least 1")
    if not expected:
        raise ValueError("recall is undefined for a question that expects no article")
    top = set(_dedupe(retrieved)[:k])
    return len(top & set(expected)) / len(set(expected))


def reciprocal_rank(retrieved: Sequence[str], expected: Collection[str]) -> float:
    """1/rank of the first relevant article, 0 when none of them was retrieved."""
    if not expected:
        raise ValueError("reciprocal rank is undefined for a question that expects no article")
    wanted = set(expected)
    for rank, article in enumerate(_dedupe(retrieved), 1):
        if article in wanted:
            return 1.0 / rank
    return 0.0


def mean(values: Sequence[float]) -> float:
    if not values:
        raise ValueError("cannot average an empty list")
    return float(sum(values) / len(values))


def mean_recall_at_k(
    runs: Sequence[tuple[Sequence[str], Collection[str]]],
    k: int,
) -> float:
    """Recall@k averaged over questions, each run being (retrieved, expected)."""
    return mean([recall_at_k(retrieved, expected, k) for retrieved, expected in runs])


def mean_reciprocal_rank(runs: Sequence[tuple[Sequence[str], Collection[str]]]) -> float:
    return mean([reciprocal_rank(retrieved, expected) for retrieved, expected in runs])


def correct_refusal_rate(outcomes: Sequence[tuple[bool, bool]]) -> float:
    """Share of the questions that had to be refused and were, from (expected, refused).

    Only rows that expect a refusal count: refusing an in-scope question is a different
    failure, measured by recall and coverage, and mixing both would hide one behind the other.
    """
    refusals = [refused for expected, refused in outcomes if expected]
    if not refusals:
        raise ValueError("no question in the batch expects a refusal")
    return sum(refusals) / len(refusals)


@dataclass(frozen=True)
class CitationCase:
    """What one answer cited, against what it could and should have cited.

    ``allowed`` holds the articles of the passages handed to the model: a citation outside
    it is invented, whatever the article says. ``expected`` comes from the golden set.
    """

    cited: tuple[str, ...]
    allowed: frozenset[str]
    expected: frozenset[str]


def raw_citation_validity(cases: Sequence[CitationCase]) -> float:
    """Share of the raw citations, before filtering, that point at a provided passage.

    With no citation at all nothing was invented, so the rate is 1; the missing citations
    are caught by coverage instead.
    """
    total = valid = 0
    for case in cases:
        cited = _dedupe(case.cited)
        total += len(cited)
        valid += sum(article in case.allowed for article in cited)
    return 1.0 if total == 0 else valid / total


def invented_citations(cases: Sequence[CitationCase]) -> int:
    """Number of distinct citations per answer that point outside the provided passages.

    Build the cases from the final answer, after the citation filter, to check the
    ``invented_in_final_answer_max`` floor: any count above zero means the filter let an
    invented reference reach the user. A count, not a rate, because the floor is zero and a
    single leak must fail the gate whatever the size of the batch.
    """
    return sum(
        sum(article not in case.allowed for article in _dedupe(case.cited)) for case in cases
    )


def citation_precision(cases: Sequence[CitationCase]) -> float:
    """Micro-averaged share of the cited articles that the golden set expected.

    No citation at all scores 0, not 1: an assistant that never cites must fail this gate.
    """
    total = hits = 0
    for case in cases:
        cited = _dedupe(case.cited)
        total += len(cited)
        hits += sum(article in case.expected for article in cited)
    return 0.0 if total == 0 else hits / total


def citation_coverage(cases: Sequence[CitationCase]) -> float:
    """Micro-averaged share of the expected articles that the answers actually cited."""
    total = hits = 0
    for case in cases:
        total += len(case.expected)
        hits += len(case.expected & set(case.cited))
    if total == 0:
        raise ValueError("coverage is undefined when no article is expected")
    return hits / total


@dataclass(frozen=True)
class Interval:
    point: float
    low: float
    high: float


def bootstrap_ci(
    items: Sequence[T],
    statistic: Callable[[Sequence[T]], float],
    *,
    draws: int,
    seed: int,
    confidence: float = 0.95,
) -> Interval:
    """Percentile bootstrap interval of ``statistic`` over resampled questions.

    Resampling whole questions, not individual citations, keeps the questions as the unit
    of variance, which is what a reader means by "on another set of questions".
    """
    if not items:
        raise ValueError("cannot bootstrap an empty sample")
    if draws < 1:
        raise ValueError("draws must be at least 1")
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be strictly between 0 and 1")
    rng = np.random.default_rng(seed)
    size = len(items)
    estimates = np.empty(draws)
    for draw in range(draws):
        picks = rng.integers(0, size, size=size)
        estimates[draw] = statistic([items[i] for i in picks])
    tail = (1.0 - confidence) / 2.0
    low, high = np.quantile(estimates, [tail, 1.0 - tail])
    return Interval(point=statistic(items), low=float(low), high=float(high))
