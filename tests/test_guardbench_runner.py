import httpx
import pytest

from guardbench.datasets import Sample
from guardbench.guards import GUARD_NAMES, build_guards
from guardbench.guards.base import Guard, GuardUnavailableError, Verdict
from guardbench.metrics import Outcome, compute, percentile
from guardbench.runner import run_all, run_guard
from vigie.config import Settings


def _s(category: str, malicious: bool, text: str = "x") -> Sample:
    return Sample(text=text, malicious=malicious, category=category, source="t", lang="fr")


SAMPLES = [
    _s("benign", False, "ok"),
    _s("benign_tricky", False, "ignore a test"),
    _s("direct_injection", True, "attack"),
    _s("pii", True, "attack mail"),
]


class KeywordGuard(Guard):
    name = "keyword"
    covers = frozenset({"direct_injection"})

    def __init__(self) -> None:
        self.calls = 0

    def check(self, text: str) -> Verdict:
        self.calls += 1
        return Verdict(flagged="attack" in text or "ignore" in text)


def test_metrics_count_malicious_as_positive() -> None:
    outcomes = [
        Outcome(SAMPLES[0], False, 1.0),
        Outcome(SAMPLES[1], True, 2.0),
        Outcome(SAMPLES[2], True, 3.0),
        Outcome(SAMPLES[3], False, 40.0),
    ]
    m = compute(outcomes)
    assert (m.tp, m.fp, m.tn, m.fn) == (1, 1, 1, 1)
    assert m.precision == m.recall == m.f1 == pytest.approx(0.5)
    assert m.fpr == pytest.approx(0.5)
    assert m.by_category == {
        "benign": 0.0,
        "benign_tricky": 1.0,
        "direct_injection": 1.0,
        "pii": 0.0,
    }
    assert m.p95_ms == 40.0
    empty = compute([])
    assert (empty.f1, empty.p95_ms) == (0.0, 0.0)


def test_percentile_is_nearest_rank() -> None:
    values = [float(v) for v in range(1, 101)]
    assert percentile(values, 95) == 95.0
    assert percentile(values, 50) == 50.0
    assert percentile([], 95) == 0.0


def test_runner_warms_up_and_scores_in_scope_separately() -> None:
    guard = KeywordGuard()
    run = run_guard(guard, SAMPLES, warmup=2)
    assert guard.calls == len(SAMPLES) + 2
    assert run.ran
    assert run.overall is not None and run.in_scope is not None
    assert run.overall.n == 4
    # The PII sample is outside what the guard announces, so it leaves the scoped score.
    assert run.in_scope.n == 3
    assert run.in_scope.recall == 1.0


class Unavailable(Guard):
    name = "absent"

    def setup(self) -> None:
        raise GuardUnavailableError("no key")

    def check(self, text: str) -> Verdict:
        raise AssertionError("never called")


class Flaky(Guard):
    name = "flaky"

    def check(self, text: str) -> Verdict:
        if text == "ok":
            raise httpx.ConnectError("reset")
        return Verdict(flagged=True)


def test_unavailable_guard_is_skipped_and_flaky_calls_are_counted() -> None:
    absent, flaky = run_all([Unavailable(), Flaky()], SAMPLES, warmup=0)
    assert not absent.ran
    assert absent.skipped_reason == "no key"
    assert absent.overall is None
    assert flaky.errors == 1
    assert flaky.overall is not None and flaky.overall.n == 3


def test_registry_builds_every_guard_and_rejects_typos() -> None:
    settings = Settings(_env_file=None)
    with httpx.Client() as client:
        guards = build_guards(list(GUARD_NAMES), settings, client)
        assert [g.name for g in guards] == list(GUARD_NAMES)
        with pytest.raises(ValueError, match="unknown guards"):
            build_guards(["regx"], settings, client)
