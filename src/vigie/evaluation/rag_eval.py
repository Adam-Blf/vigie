"""Citation and refusal rates of the whole pipeline on one split of the golden set.

With the fake LLM these numbers check the plumbing, not the model: the fake cites the
first passages it is given, so precision and coverage follow retrieval, and it never
refuses on its own. What it does prove is the filter. Run with FAKE_LLM_HALLUCINATE=1,
every answer carries one invented citation; a raw validity below 1 shows they were
written, zero invented citations in the final answers shows they were all removed.

Refusals are counted on the out-of-scope rows of the split for a dev run. For the test
split they are counted on all ten out-of-scope rows, dev and test, as data/golden/README.md
explains: three test rows alone would move the rate by 33 points per miss.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from vigie.evaluation.golden import GoldenQuestion, Split
from vigie.evaluation.metrics import (
    CitationCase,
    citation_coverage,
    citation_precision,
    correct_refusal_rate,
    invented_citations,
    raw_citation_validity,
)
from vigie.rag.citations import extract_citations
from vigie.rag.pipeline import RagPipeline
from vigie.rag.types import Answer


@dataclass(frozen=True)
class RagRow:
    id: str
    refused: bool
    expects_refusal: bool
    cited: tuple[str, ...]
    removed: tuple[str, ...]
    allowed: tuple[str, ...]
    expected: tuple[str, ...]


@dataclass(frozen=True)
class RagResult:
    rows: tuple[RagRow, ...]
    raw_citation_validity: float
    invented_in_final_answer: int
    citation_precision: float
    citation_coverage: float
    correct_refusal_rate: float | None
    refusal_rows: int


def _row(question: GoldenQuestion, answer: Answer) -> RagRow:
    removed = tuple(
        f"{raw.regulation}:{raw.article}"
        for label in answer.removed_citations
        for raw in extract_citations(label)
    )
    return RagRow(
        id=question.id,
        refused=answer.refused,
        expects_refusal=question.expects_refusal,
        cited=tuple(dict.fromkeys(f"{c.regulation}:{c.article}" for c in answer.citations)),
        removed=removed,
        allowed=tuple(dict.fromkeys(p.article_id for p in answer.sources)),
        expected=question.expected_articles,
    )


def final_cases(rows: Sequence[RagRow]) -> list[CitationCase]:
    """What each answer finally cited; only rows that expect articles."""
    return [
        CitationCase(r.cited, frozenset(r.allowed), frozenset(r.expected))
        for r in rows
        if r.expected
    ]


def raw_cases(rows: Sequence[RagRow]) -> list[CitationCase]:
    """What each answer cited before the filter: kept citations plus removed ones."""
    return [
        CitationCase(r.cited + r.removed, frozenset(r.allowed), frozenset(r.expected))
        for r in rows
        if r.expected
    ]


def _in_refusal_scope(question: GoldenQuestion, split: Split) -> bool:
    if not question.expects_refusal:
        return False
    return split == "test" or question.split == split


def evaluate_rag(
    questions: Sequence[GoldenQuestion], pipeline: RagPipeline, *, split: Split
) -> RagResult:
    rows: list[RagRow] = []
    for question in questions:
        if question.split == split or _in_refusal_scope(question, split):
            rows.append(_row(question, pipeline.answer(question.question)))
    # Rows borrowed from the other split are out-of-scope ones, which expect no article,
    # so the citation figures below only ever see rows of the requested split.
    answered = [r for r in rows if r.expected]
    if not answered:
        raise ValueError(f"no question of the {split} split expects an article")
    finals = final_cases(answered)
    refusal = [(r.expects_refusal, r.refused) for r in rows if r.expects_refusal]
    return RagResult(
        rows=tuple(rows),
        raw_citation_validity=raw_citation_validity(raw_cases(answered)),
        invented_in_final_answer=invented_citations(finals),
        citation_precision=citation_precision(finals),
        citation_coverage=citation_coverage(finals),
        correct_refusal_rate=correct_refusal_rate(refusal) if refusal else None,
        refusal_rows=len(refusal),
    )
