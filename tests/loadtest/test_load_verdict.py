import pytest

from vigie.config import Settings
from vigie.loadtest.verdict import LoadResult, LoadThresholds, violations

THRESHOLDS = LoadThresholds(p95_ms=500.0, max_error_ratio=0.01, max_attack_leak_ratio=0.10)


def _result(**overrides: float) -> LoadResult:
    values: dict[str, float] = {
        "requests": 1000,
        "failures": 0,
        "p95_ms": 120.0,
        "attacks": 100,
        "attack_leaks": 0,
    }
    values.update(overrides)
    return LoadResult(
        requests=int(values["requests"]),
        failures=int(values["failures"]),
        p95_ms=values["p95_ms"],
        attacks=int(values["attacks"]),
        attack_leaks=int(values["attack_leaks"]),
    )


def test_healthy_run_passes() -> None:
    assert violations(_result(), THRESHOLDS) == []


def test_p95_must_stay_strictly_under_the_limit() -> None:
    assert violations(_result(p95_ms=499.0), THRESHOLDS) == []
    (problem,) = violations(_result(p95_ms=500.0), THRESHOLDS)
    assert problem.startswith("p95 500 ms")


def test_error_ratio_must_stay_strictly_under_one_percent() -> None:
    assert violations(_result(failures=9), THRESHOLDS) == []
    (problem,) = violations(_result(failures=10), THRESHOLDS)
    assert "1.00% (10/1000)" in problem


def test_attack_leaks_up_to_the_recall_floor_pass() -> None:
    assert violations(_result(attack_leaks=10), THRESHOLDS) == []
    (problem,) = violations(_result(attack_leaks=11), THRESHOLDS)
    assert problem.startswith("attack leak ratio 11.00%")


def test_run_without_attacks_is_judged_on_the_rest() -> None:
    assert violations(_result(attacks=0, attack_leaks=0), THRESHOLDS) == []


def test_run_without_traffic_fails() -> None:
    assert violations(_result(requests=0, failures=0), THRESHOLDS) == [
        "no request was measured, the run proves nothing"
    ]


def test_every_missed_threshold_is_reported() -> None:
    assert len(violations(_result(p95_ms=900.0, failures=50, attack_leaks=40), THRESHOLDS)) == 3


def test_settings_defaults_match_the_brief() -> None:
    settings = Settings(_env_file=None)
    assert settings.load_token is None
    assert (
        settings.load_p95_ms,
        settings.load_max_error_ratio,
        settings.load_max_attack_leak_ratio,
    ) == (500.0, 0.01, 0.10)


def test_load_token_is_read_from_the_environment_and_masked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIGIE_LOAD_TOKEN", "vig_local_test_value")
    settings = Settings(_env_file=None)
    assert settings.load_token is not None
    assert settings.load_token.get_secret_value() == "vig_local_test_value"
    assert "vig_local_test_value" not in repr(settings)
