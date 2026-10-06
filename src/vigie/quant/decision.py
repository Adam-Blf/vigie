"""The int8 or fp32 decision, read from a threshold written before the measurement.

The rule is the brief's: int8 replaces fp32 only if recall@5 drops by at most two points
and the model file is at least halved. Both conditions are checked, so a model that is
smaller but much worse, or as good but barely smaller, stays out.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

# Recall values are means of fractions, so a drop of exactly 0.02 can come out as
# 0.020000000000000018. Without this tolerance the threshold would be stricter than written.
_EPSILON = 1e-9


class QuantThreshold(BaseModel):
    """The ``quantization`` section of eval/thresholds.yaml."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    split: Literal["dev"]
    k: int = Field(ge=1)
    max_recall_drop: float = Field(ge=0.0, le=1.0)
    max_size_ratio: float = Field(gt=0.0, le=1.0)


def load_threshold(path: Path) -> QuantThreshold:
    """Read the threshold; a test split there is refused by the model, on purpose."""
    document: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or "quantization" not in document:
        raise ValueError(f"{path} has no quantization section")
    return QuantThreshold.model_validate(document["quantization"])


@dataclass(frozen=True)
class VariantResult:
    """What one embedding variant measured on the dev split."""

    name: str
    size_bytes: int
    recall_at_k: float
    mrr: float
    latency_p50_ms: float
    latency_p95_ms: float
    questions: int


@dataclass(frozen=True)
class Decision:
    keep_int8: bool
    recall_drop: float
    size_ratio: float
    reasons: tuple[str, ...]

    @property
    def deployed(self) -> Literal["fp32", "int8"]:
        return "int8" if self.keep_int8 else "fp32"


def decide(
    *, recall_drop: float, size_ratio: float, threshold: QuantThreshold
) -> tuple[bool, tuple[str, ...]]:
    """Keep int8 iff the recall drop and the size ratio both stay within the threshold."""
    reasons: list[str] = []
    recall_ok = recall_drop <= threshold.max_recall_drop + _EPSILON
    size_ok = size_ratio <= threshold.max_size_ratio + _EPSILON
    if not recall_ok:
        reasons.append(
            f"recall@{threshold.k} drops by {recall_drop * 100:.1f} points, "
            f"more than {threshold.max_recall_drop * 100:.1f}"
        )
    if not size_ok:
        reasons.append(
            f"int8 file is {size_ratio:.2f} of fp32, above {threshold.max_size_ratio:.2f}"
        )
    return recall_ok and size_ok, tuple(reasons)


def compare(fp32: VariantResult, int8: VariantResult, threshold: QuantThreshold) -> Decision:
    if fp32.size_bytes <= 0:
        raise ValueError("the fp32 model size must be positive")
    if fp32.questions != int8.questions:
        raise ValueError("both variants must be measured on the same questions")
    recall_drop = fp32.recall_at_k - int8.recall_at_k
    size_ratio = int8.size_bytes / fp32.size_bytes
    keep, reasons = decide(recall_drop=recall_drop, size_ratio=size_ratio, threshold=threshold)
    return Decision(keep, recall_drop, size_ratio, reasons)
