"""One evaluation run: retrieval metrics, pipeline metrics, confidence intervals, config.

The result is a plain dictionary, the report. The same object is written to disk, logged
to MLflow, read back by the gate and turned into the release bundle, so there is one
description of a run and not three that could disagree.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, TypeVar

from vigie.evaluation.golden import GoldenQuestion, Split
from vigie.evaluation.metrics import Interval, bootstrap_ci, citation_coverage, citation_precision
from vigie.evaluation.rag_eval import RagResult, RagRow, evaluate_rag, final_cases
from vigie.evaluation.retrieval_eval import RetrievalResult, RetrievalRow, evaluate_retrieval
from vigie.evaluation.thresholds import Thresholds
from vigie.rag.pipeline import RagPipeline, Retriever

T = TypeVar("T")


def _interval(
    items: Sequence[T], statistic: Callable[[Sequence[T]], float], t: Thresholds
) -> dict[str, float]:
    found: Interval = bootstrap_ci(
        items,
        statistic,
        draws=t.bootstrap_draws,
        seed=t.bootstrap_seed,
        confidence=t.bootstrap_confidence,
    )
    return {"point": found.point, "low": found.low, "high": found.high}


def _mean_of(field: str) -> Callable[[Sequence[RetrievalRow]], float]:
    def statistic(rows: Sequence[RetrievalRow]) -> float:
        return sum(float(getattr(r, field)) for r in rows) / len(rows)

    return statistic


def _cases_stat(
    metric: Callable[[Sequence[Any]], float],
) -> Callable[[Sequence[RagRow]], float]:
    def statistic(rows: Sequence[RagRow]) -> float:
        return metric(final_cases(rows))

    return statistic


def confidence_intervals(
    retrieval: RetrievalResult, rag: RagResult | None, t: Thresholds
) -> dict[str, dict[str, float]]:
    """Percentile bootstrap over questions, 1 000 draws with the seed of the thresholds."""
    intervals = {
        "recall_at_k": _interval(retrieval.rows, _mean_of("recall_at_k"), t),
        "mrr": _interval(retrieval.rows, _mean_of("reciprocal_rank"), t),
    }
    if rag is not None:
        answered = [r for r in rag.rows if r.expected]
        intervals["citation_precision"] = _interval(answered, _cases_stat(citation_precision), t)
        intervals["citation_coverage"] = _interval(answered, _cases_stat(citation_coverage), t)
    return intervals


def build_report(
    questions: Sequence[GoldenQuestion],
    retriever: Retriever,
    *,
    split: Split,
    depth: int,
    thresholds: Thresholds,
    config: dict[str, str],
    pipeline: RagPipeline | None,
    llm: str,
) -> dict[str, Any]:
    retrieval = evaluate_retrieval(questions, retriever, split=split, k=thresholds.k, depth=depth)
    rag = evaluate_rag(questions, pipeline, split=split) if pipeline else None
    metrics: dict[str, float | None] = {
        "recall_at_k": retrieval.recall_at_k,
        "mrr": retrieval.mrr,
    }
    if rag is not None:
        metrics.update(
            raw_citation_validity=rag.raw_citation_validity,
            invented_in_final_answer=float(rag.invented_in_final_answer),
            citation_precision=rag.citation_precision,
            citation_coverage=rag.citation_coverage,
            correct_refusal_rate=rag.correct_refusal_rate,
        )
    return {
        "split": split,
        "llm": llm,
        "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "config": config,
        "counts": {
            "retrieval_questions": retrieval.questions,
            "rag_rows": len(rag.rows) if rag else 0,
            "refusal_rows": rag.refusal_rows if rag else 0,
        },
        "metrics": metrics,
        "ci": confidence_intervals(retrieval, rag, thresholds),
        "retrieval_rows": [asdict(r) for r in retrieval.rows],
        "rag_rows": [asdict(r) for r in rag.rows] if rag else [],
    }
