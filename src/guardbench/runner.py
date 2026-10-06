"""Run each guard over the samples and time every call.

Warm-up calls are made first and not timed: the first call of a transformer pays for
lazy allocations and the first HTTP call pays for the TLS handshake, neither of which a
production request sees.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass, field

import httpx

from guardbench.datasets import BENIGN_CATEGORIES, Sample
from guardbench.guards.base import Guard, GuardUnavailableError
from guardbench.metrics import Metrics, Outcome, compute


@dataclass
class GuardRun:
    name: str
    covers: frozenset[str]
    skipped_reason: str | None = None
    outcomes: list[Outcome] = field(default_factory=list)
    errors: int = 0
    overall: Metrics | None = None
    in_scope: Metrics | None = None

    @property
    def ran(self) -> bool:
        return self.skipped_reason is None


def in_scope(outcomes: Sequence[Outcome], covers: frozenset[str]) -> list[Outcome]:
    # Benign samples always stay in scope: a narrow tool still has to leave normal
    # questions alone.
    return [o for o in outcomes if o.sample.category in covers | BENIGN_CATEGORIES]


def run_guard(guard: Guard, samples: Sequence[Sample], warmup: int) -> GuardRun:
    run = GuardRun(name=guard.name, covers=guard.covers)
    try:
        guard.setup()
        for sample in samples[:warmup]:
            guard.check(sample.text)
        for sample in samples:
            start = time.perf_counter()
            try:
                verdict = guard.check(sample.text)
            except httpx.HTTPError:
                # A single failed remote call should not erase the whole run, but it is
                # counted and printed so a flaky service cannot pass for a clean one.
                run.errors += 1
                continue
            elapsed_ms = (time.perf_counter() - start) * 1000
            run.outcomes.append(Outcome(sample, verdict.flagged, elapsed_ms))
    except GuardUnavailableError as exc:
        run.skipped_reason = str(exc)
        run.outcomes.clear()
        return run
    run.overall = compute(run.outcomes)
    run.in_scope = compute(in_scope(run.outcomes, guard.covers))
    return run


def pin_torch_threads(threads: int) -> bool:
    """Cap torch intra-op threads so CPU models are timed under the production budget."""
    try:
        import torch
    except ImportError:
        return False
    torch.set_num_threads(threads)
    return True


def run_all(guards: Sequence[Guard], samples: Sequence[Sample], warmup: int) -> list[GuardRun]:
    return [run_guard(guard, samples, warmup) for guard in guards]
