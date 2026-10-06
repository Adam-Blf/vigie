"""Checks a golden set has to pass before any number computed on it can be trusted.

Each rule exists because the matching mistake would silently inflate or deflate a metric:
an unknown article can never be retrieved, a quote that is not in the text means the
reference answer was written from memory, and a draft row was never checked by the second
member of the pair.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from vigie.evaluation.corpus_text import normalize_space
from vigie.evaluation.golden import TEST_SHARE_DENOMINATOR, GoldenQuestion, sealed_digest
from vigie.evaluation.regulations import REGULATION_CELEX, split_article_id

# Bounds on the test share. Strata are rounded one by one, so the global share drifts a
# little from one third; anything outside these bounds means the split field was edited.
_TEST_SHARE_MIN = 0.25
_TEST_SHARE_MAX = 0.40


@dataclass(frozen=True)
class Issue:
    question_id: str
    message: str

    def __str__(self) -> str:
        return f"{self.question_id}: {self.message}"


@dataclass
class Report:
    issues: list[Issue] = field(default_factory=list)
    counts: dict[str, Counter[str]] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.issues


def _check_row(question: GoldenQuestion, corpus: Mapping[str, str]) -> list[str]:
    problems: list[str] = []
    if question.status != "verified":
        problems.append(f"status is {question.status!r}, only verified rows are accepted")
    if not question.verified_by:
        problems.append("verified_by is empty")
    elif question.verified_by == question.authored_by:
        problems.append("verified by its own author, the other member of the pair must check")
    if question.split is None:
        problems.append("split is missing")

    if question.expects_refusal:
        if question.expected_articles or question.reference_quote or question.source_celex:
            problems.append("an out-of-scope question cannot expect articles or a quote")
        return problems

    if not question.expected_articles:
        return [*problems, "no expected article for a question that should be answered"]
    for article in question.expected_articles:
        try:
            regulation, _ = split_article_id(article)
        except ValueError as exc:
            problems.append(str(exc))
            continue
        if article not in corpus:
            problems.append(f"unknown article {article}")
        elif REGULATION_CELEX[regulation] != question.source_celex:
            problems.append(f"{article} does not belong to CELEX {question.source_celex}")
    if not question.reference_quote:
        problems.append("reference_quote is empty")
    else:
        quote = normalize_space(question.reference_quote)
        texts = (corpus.get(article, "") for article in question.expected_articles)
        if not any(quote in text for text in texts):
            problems.append("reference_quote not found in the text of the expected articles")
    return problems


def _counts(questions: Sequence[GoldenQuestion]) -> dict[str, Counter[str]]:
    regulation: Counter[str] = Counter()
    for question in questions:
        for code in sorted(question.regulations) or ["none"]:
            regulation[code] += 1
    return {
        "regulation": regulation,
        "lang": Counter(q.lang for q in questions),
        "category": Counter(q.category for q in questions),
        "split": Counter(q.split or "missing" for q in questions),
    }


def validate_golden(
    questions: Sequence[GoldenQuestion],
    corpus: Mapping[str, str],
    seal: str | None,
) -> Report:
    """Run every rule and collect all problems at once, so one run lists everything to fix."""
    report = Report(counts=_counts(questions))
    seen: set[str] = set()
    for question in questions:
        if question.id in seen:
            report.issues.append(Issue(question.id, "duplicate id"))
        seen.add(question.id)
        report.issues.extend(Issue(question.id, p) for p in _check_row(question, corpus))

    if questions:
        share = report.counts["split"]["test"] / len(questions)
        if not _TEST_SHARE_MIN <= share <= _TEST_SHARE_MAX:
            expected = f"about 1/{TEST_SHARE_DENOMINATOR}"
            report.issues.append(Issue("*", f"test share is {share:.2f}, expected {expected}"))
    if seal is None:
        report.issues.append(Issue("*", "no test seal, run seal-golden once the set is final"))
    elif seal != sealed_digest(questions):
        report.issues.append(Issue("*", "test split differs from its seal (test.sha256)"))
    return report
