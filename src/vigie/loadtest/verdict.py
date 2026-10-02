"""Turn the numbers of a finished run into a pass or fail verdict.

Locust exits with 0 whenever the run itself went fine, even if the service was slow. The
verdict below sets the process exit code, so a run that misses a threshold fails in a
terminal or a CI job the same way a red test would.

Attack prompts are judged apart from latency and errors. A prompt that slips past the
guard is a guard quality problem, not an availability one, and mixing both would let a
leaky guard look like a flaky API (or the reverse).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LoadThresholds:
    p95_ms: float
    max_error_ratio: float
    max_attack_leak_ratio: float


@dataclass(frozen=True)
class LoadResult:
    """Raw counters of a run, attack requests excluded from ``requests`` and ``failures``."""

    requests: int
    failures: int
    p95_ms: float
    attacks: int
    attack_leaks: int


def _ratio(part: int, whole: int) -> float:
    return part / whole if whole else 0.0


def violations(result: LoadResult, thresholds: LoadThresholds) -> list[str]:
    """Every threshold the run missed, as readable lines. Empty means the run passes."""
    problems: list[str] = []
    if result.requests == 0:
        # No traffic is not a success: it usually means the API was never reached.
        return ["no request was measured, the run proves nothing"]
    if result.p95_ms >= thresholds.p95_ms:
        problems.append(f"p95 {result.p95_ms:.0f} ms, limit {thresholds.p95_ms:.0f} ms")
    error_ratio = _ratio(result.failures, result.requests)
    if error_ratio >= thresholds.max_error_ratio:
        problems.append(
            f"error ratio {error_ratio:.2%} ({result.failures}/{result.requests}), "
            f"limit {thresholds.max_error_ratio:.2%}"
        )
    leak_ratio = _ratio(result.attack_leaks, result.attacks)
    if leak_ratio > thresholds.max_attack_leak_ratio:
        problems.append(
            f"attack leak ratio {leak_ratio:.2%} ({result.attack_leaks}/{result.attacks}), "
            f"limit {thresholds.max_attack_leak_ratio:.2%}"
        )
    return problems
