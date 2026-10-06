"""Read eval/thresholds.yaml into a typed object.

The file is the contract; this module only refuses a file that lacks a floor, so a key
renamed by mistake fails loudly instead of turning a gate into a check against nothing.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class Thresholds:
    split: str
    k: int
    recall_at_k_min: float
    mrr_min: float
    invented_in_final_answer_max: int
    precision_min: float
    coverage_min: float
    correct_refusal_rate_min: float
    max_drop: float
    regression_metrics: tuple[str, ...]
    bootstrap_draws: int
    bootstrap_seed: int
    bootstrap_confidence: float


def _section(data: dict[str, Any], name: str) -> dict[str, Any]:
    value = data.get(name)
    if not isinstance(value, dict):
        raise ValueError(f"thresholds file has no {name} section")
    return value


def parse_thresholds(data: dict[str, Any]) -> Thresholds:
    retrieval = _section(data, "retrieval")
    citations = _section(data, "citations")
    refusal = _section(data, "refusal")
    regression = _section(data, "regression")
    bootstrap = _section(data, "bootstrap")
    try:
        return Thresholds(
            split=str(data["split"]),
            k=int(retrieval["k"]),
            recall_at_k_min=float(retrieval["recall_at_k_min"]),
            mrr_min=float(retrieval["mrr_min"]),
            invented_in_final_answer_max=int(citations["invented_in_final_answer_max"]),
            precision_min=float(citations["precision_min"]),
            coverage_min=float(citations["coverage_min"]),
            correct_refusal_rate_min=float(refusal["correct_refusal_rate_min"]),
            max_drop=float(regression["max_drop"]),
            regression_metrics=tuple(str(m) for m in regression["metrics"]),
            bootstrap_draws=int(bootstrap["draws"]),
            bootstrap_seed=int(bootstrap["seed"]),
            bootstrap_confidence=float(bootstrap["confidence"]),
        )
    except KeyError as missing:
        raise ValueError(f"thresholds file lacks {missing.args[0]}") from missing


def load_thresholds(path: Path) -> Thresholds:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} is not a mapping")
    return parse_thresholds(data)
