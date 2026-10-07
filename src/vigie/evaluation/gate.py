"""The evaluation gate: floors from eval/thresholds.yaml, then no regression on the champion.

Two kinds of checks. Floors are absolute (recall@5 at least 0.80, and so on). The relative
check compares with the champion, the configuration in production: recall@k and raw
citation validity may not drop by more than `max_drop` (2 points), even above the floor,
so a slow slide cannot go unnoticed one point at a time.

Precision, coverage and refusal depend on the model. Against the fake LLM they say how
retrieval and the citation filter behave, not how the assistant answers, so they are
reported but only gated for a real LLM. Recall, MRR and the zero invented citations of
the final answers are deterministic and always gated.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from vigie.evaluation.thresholds import Thresholds
from vigie.llm.fake import FAKE_MODEL


@dataclass(frozen=True)
class Check:
    name: str
    value: float | None
    limit: float
    rule: str
    ok: bool
    note: str = ""

    def line(self) -> str:
        shown = "n/a" if self.value is None else f"{self.value:.4f}"
        status = "PASS" if self.ok else "FAIL"
        tail = f"  ({self.note})" if self.note else ""
        return f"{status}  {self.name:<32} {shown:>8} {self.rule} {self.limit:.4f}{tail}"


def _floor(name: str, value: float | None, limit: float, *, at_most: bool = False) -> Check:
    rule = "<=" if at_most else ">="
    if value is None:
        return Check(name, None, limit, rule, False, "missing from the report")
    ok = value <= limit if at_most else value >= limit
    return Check(name, value, limit, rule, ok)


def _model_floor(name: str, value: float | None, limit: float, *, gated: bool) -> Check:
    check = _floor(name, value, limit)
    if gated:
        return check
    return Check(name, value, limit, check.rule, True, "fake LLM, reported only")


def floor_checks(metrics: Mapping[str, float | None], llm: str, t: Thresholds) -> list[Check]:
    real_llm = llm != FAKE_MODEL
    return [
        _floor("recall_at_k", metrics.get("recall_at_k"), t.recall_at_k_min),
        _floor("mrr", metrics.get("mrr"), t.mrr_min),
        _floor(
            "invented_in_final_answer",
            metrics.get("invented_in_final_answer"),
            t.invented_in_final_answer_max,
            at_most=True,
        ),
        _model_floor(
            "citation_precision",
            metrics.get("citation_precision"),
            t.precision_min,
            gated=real_llm,
        ),
        _model_floor(
            "citation_coverage",
            metrics.get("citation_coverage"),
            t.coverage_min,
            gated=real_llm,
        ),
        _model_floor(
            "correct_refusal_rate",
            metrics.get("correct_refusal_rate"),
            t.correct_refusal_rate_min,
            gated=real_llm,
        ),
    ]


def regression_checks(
    metrics: Mapping[str, float | None],
    baseline: Mapping[str, float | None],
    t: Thresholds,
) -> list[Check]:
    checks: list[Check] = []
    for name in t.regression_metrics:
        current, reference = metrics.get(name), baseline.get(name)
        label = f"{name} vs champion"
        if reference is None:
            checks.append(Check(label, current, t.max_drop, "drop <=", True, "no champion value"))
            continue
        if current is None:
            checks.append(Check(label, None, t.max_drop, "drop <=", False, "missing"))
            continue
        drop = reference - current
        # A float sum like 0.80 - 0.78 lands a hair above 0.02; a drop of exactly the
        # allowed two points must pass.
        ok = drop <= t.max_drop + 1e-9
        checks.append(Check(label, drop, t.max_drop, "drop <=", ok, f"champion {reference:.4f}"))
    return checks


def run_gate(
    report: Mapping[str, object],
    thresholds: Thresholds,
    baseline: Mapping[str, object] | None = None,
) -> list[Check]:
    metrics = _metrics(report)
    llm = str(report.get("llm", FAKE_MODEL))
    checks = floor_checks(metrics, llm, thresholds)
    if report.get("split") != thresholds.split:
        checks.append(
            Check("split", None, 0.0, "==", False, f"floors are set on {thresholds.split}")
        )
    if baseline is not None:
        checks.extend(regression_checks(metrics, _metrics(baseline), thresholds))
    return checks


def _metrics(report: Mapping[str, object]) -> dict[str, float | None]:
    raw = report.get("metrics")
    if not isinstance(raw, Mapping):
        raise ValueError("the report has no metrics section")
    return {str(k): None if v is None else float(v) for k, v in raw.items()}


def passed(checks: list[Check]) -> bool:
    return all(c.ok for c in checks)
