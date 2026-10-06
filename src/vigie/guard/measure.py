"""Measure the production input chain against the guard thresholds of eval/thresholds.yaml.

    python -m vigie.guard.measure [--split test] [--out results/guard]

Every sample goes through the same path as a question sent to the API: normalization,
then the chain. The guardbench runner does the timing, with its untimed warm-up calls, so
these numbers compare directly with the benchmark report. The command exits 1 when a
threshold is missed, which makes it usable as a gate.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TextIO

import yaml

from guardbench.datasets import CATEGORIES, Sample, load_seed
from guardbench.guards.base import Guard, Verdict
from guardbench.metrics import Outcome, compute
from guardbench.runner import run_guard
from vigie.config import Settings, get_settings
from vigie.guard.base import InputGuard
from vigie.guard.factory import build_input_guard
from vigie.guard.normalize import normalize

THRESHOLDS_PATH = Path("eval/thresholds.yaml")


class ChainUnderTest(Guard):
    """The API's view of the chain, wrapped in the benchmark's guard interface."""

    name = "vigie-input-chain"
    covers = frozenset(CATEGORIES)

    def __init__(self, chain: InputGuard) -> None:
        self._chain = chain

    def check(self, text: str) -> Verdict:
        decision = self._chain.check(normalize(text).guard_view)
        return Verdict(decision.blocked, decision.labels, decision.score)


@dataclass
class GuardReport:
    split: str
    samples: int
    direct_injection_recall: dict[str, float]
    benign_fpr: float
    benign_tricky_fpr: float
    p50_ms: float
    p95_ms: float
    by_category: dict[str, float]
    checks: dict[str, bool] = field(default_factory=dict)
    errors: list[dict[str, Any]] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(self.checks.values())


def _rate(outcomes: Sequence[Outcome]) -> float:
    return sum(o.flagged for o in outcomes) / len(outcomes) if outcomes else 0.0


def evaluate(outcomes: Sequence[Outcome], thresholds: dict[str, float], split: str) -> GuardReport:
    metrics = compute(outcomes)
    direct = [o for o in outcomes if o.sample.category == "direct_injection"]
    recall = {lang: _rate([o for o in direct if o.sample.lang == lang]) for lang in ("fr", "en")}
    recall["all"] = _rate(direct)
    report = GuardReport(
        split=split,
        samples=len(outcomes),
        direct_injection_recall=recall,
        benign_fpr=metrics.by_category.get("benign", 0.0),
        benign_tricky_fpr=metrics.by_category.get("benign_tricky", 0.0),
        p50_ms=round(metrics.p50_ms, 2),
        p95_ms=round(metrics.p95_ms, 2),
        by_category=metrics.by_category,
    )
    floor = thresholds["direct_injection_recall_min"]
    report.checks = {
        "direct_injection_recall_fr": recall["fr"] >= floor,
        "direct_injection_recall_en": recall["en"] >= floor,
        "benign_fpr": report.benign_fpr <= thresholds["benign_fpr_max"],
        "benign_tricky_fpr": report.benign_tricky_fpr <= thresholds["benign_tricky_fpr_max"],
        "p95_ms": report.p95_ms < thresholds["p95_ms"],
    }
    report.errors = [
        {"category": o.sample.category, "lang": o.sample.lang, "pair_id": o.sample.pair_id}
        for o in outcomes
        if o.flagged != o.sample.malicious
    ]
    return report


def load_thresholds(path: Path = THRESHOLDS_PATH) -> dict[str, float]:
    section: dict[str, float] = yaml.safe_load(path.read_text(encoding="utf-8"))["guard"]
    return section


def measure(
    settings: Settings, split: str, chain: InputGuard | None = None
) -> tuple[GuardReport, list[Sample]]:
    samples = load_seed(settings.bench_seed_path, split)
    guard = ChainUnderTest(chain if chain is not None else build_input_guard(settings))
    run = run_guard(guard, samples, settings.bench_warmup_calls)
    return evaluate(run.outcomes, load_thresholds(), split), samples


def render(report: GuardReport) -> str:
    def pct(value: float) -> str:
        return f"{value * 100:.1f} %"

    rows = [
        ("Rappel injections directes FR", pct(report.direct_injection_recall["fr"]), "fr"),
        ("Rappel injections directes EN", pct(report.direct_injection_recall["en"]), "en"),
        ("Faux positifs benign", pct(report.benign_fpr), "benign_fpr"),
        ("Faux positifs benign_tricky", pct(report.benign_tricky_fpr), "benign_tricky_fpr"),
        ("p95 de la chaîne (ms)", f"{report.p95_ms:.1f}", "p95_ms"),
    ]
    keys = {"fr": "direct_injection_recall_fr", "en": "direct_injection_recall_en"}
    lines = [f"Split {report.split}, {report.samples} exemples", "", "| Mesure | Valeur | Seuil |"]
    lines.append("|---|---|---|")
    for label, value, key in rows:
        verdict = "atteint" if report.checks[keys.get(key, key)] else "MANQUÉ"
        lines.append(f"| {label} | {value} | {verdict} |")
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None, out: TextIO = sys.stdout) -> int:
    parser = argparse.ArgumentParser(prog="python -m vigie.guard.measure", description=__doc__)
    parser.add_argument("--split", default="test", choices=["dev", "test"])
    parser.add_argument("--out", type=Path, default=Path("results/guard"))
    args = parser.parse_args(argv)

    report, _ = measure(get_settings(), args.split)
    args.out.mkdir(parents=True, exist_ok=True)
    payload = {**vars(report), "passed": report.passed}
    (args.out / f"guard-{args.split}.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    out.write(render(report))
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
