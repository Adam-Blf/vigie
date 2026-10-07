from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pytest

from vigie.config import Settings
from vigie.infra import retry
from vigie.infra.retry import RetryPlan, is_retryable, retry_apply, run_terraform

CAPACITY = "Error: 500-InternalError, Out of host capacity. ocid1.instance.oc1..abc"


class FakeTerraform:
    """Replays scripted apply results and records every call."""

    def __init__(self, applies: list[tuple[int, str]], init: tuple[int, str] = (0, "ok")) -> None:
        self.applies = list(applies)
        self.init = init
        self.calls: list[list[str]] = []

    def __call__(self, cmd: Sequence[str], cwd: Path) -> tuple[int, str]:
        self.calls.append(list(cmd))
        if cmd[1] == "init":
            return self.init
        return self.applies.pop(0)


def make_plan(tmp_path: Path, max_attempts: int = 5) -> RetryPlan:
    return RetryPlan(
        terraform="terraform",
        workdir=tmp_path,
        state_path=tmp_path / "state" / "terraform.tfstate",
        log_path=tmp_path / "state" / "retry.log",
        interval_s=600.0,
        max_attempts=max_attempts,
    )


def test_capacity_errors_are_retried_until_success(tmp_path: Path) -> None:
    fake = FakeTerraform([(1, CAPACITY), (1, CAPACITY), (0, "Apply complete! 81.2.69.160")])
    sleeps: list[float] = []
    assert retry_apply(make_plan(tmp_path), fake, sleeps.append) == 0
    assert sleeps == [600.0, 600.0]
    log = (tmp_path / "state" / "retry.log").read_text(encoding="utf-8")
    assert "attempt 3: apply succeeded" in log
    # The log must be safe to paste: no OCID, no public IP.
    assert "ocid1." not in log
    assert "81.2.69.160" not in log


def test_other_errors_stop_immediately(tmp_path: Path) -> None:
    fake = FakeTerraform([(1, "Error: 401-NotAuthenticated")])
    sleeps: list[float] = []
    assert retry_apply(make_plan(tmp_path), fake, sleeps.append) == 1
    assert sleeps == []
    assert "non-capacity error" in (tmp_path / "state" / "retry.log").read_text(encoding="utf-8")


def test_attempts_are_bounded(tmp_path: Path) -> None:
    fake = FakeTerraform([(1, CAPACITY)] * 3)
    sleeps: list[float] = []
    assert retry_apply(make_plan(tmp_path, max_attempts=3), fake, sleeps.append) == 1
    # No pointless wait after the last attempt.
    assert len(sleeps) == 2
    assert "k3d fallback" in (tmp_path / "state" / "retry.log").read_text(encoding="utf-8")


def test_failed_init_never_applies(tmp_path: Path) -> None:
    fake = FakeTerraform([], init=(1, "Error: backend"))
    assert retry_apply(make_plan(tmp_path), fake, lambda _: None) == 1
    assert [call[1] for call in fake.calls] == ["init"]


def test_state_path_is_passed_at_init(tmp_path: Path) -> None:
    plan = make_plan(tmp_path)
    assert plan.init_cmd()[-1] == f"-backend-config=path={plan.state_path.as_posix()}"
    assert "-auto-approve" in plan.apply_cmd()


def test_rate_limits_are_retryable() -> None:
    assert is_retryable("429-TooManyRequests")
    assert not is_retryable("Error: 404-NotAuthorizedOrNotFound")


def test_slow_provider_start_is_retryable() -> None:
    # EN: seen twice on 2026-10-07 while the laptop was busy building images.
    # FR : vu deux fois le 07/10/2026 pendant que le poste construisait des images.
    slow = (
        'failed to instantiate provider "registry.terraform.io/oracle/oci" to obtain schema: '
        "timeout while waiting for plugin to start"
    )
    assert is_retryable(slow)
    assert not is_retryable("Error: Invalid provider configuration")


def test_plan_reads_settings(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, infra_state_dir=tmp_path, infra_retry_interval_s=120)
    plan = RetryPlan.from_settings(settings, "terraform", tmp_path)
    assert plan.state_path == tmp_path / "terraform.tfstate"
    assert plan.log_path == tmp_path / "retry.log"
    assert plan.workdir == (tmp_path / "infra" / "terraform").resolve()
    assert plan.interval_s == 120.0
    assert plan.max_attempts == 1008


def test_run_terraform_captures_output_and_quiets_oci(tmp_path: Path) -> None:
    import sys

    code, out = run_terraform(
        [sys.executable, "-c", "import os; print(os.environ['SUPPRESS_LABEL_WARNING'])"],
        tmp_path,
    )
    assert code == 0
    assert out.strip() == "True"


def test_main_requires_terraform(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(retry.shutil, "which", lambda _: None)
    assert retry.main(tmp_path) == 2


def test_main_requires_tfvars(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(retry.shutil, "which", lambda _: "terraform")
    assert retry.main(tmp_path) == 2


def test_main_runs_the_loop(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / "infra" / "terraform").mkdir(parents=True)
    (tmp_path / "infra" / "terraform" / "terraform.tfvars").write_text("x = 1\n", encoding="utf-8")
    monkeypatch.setattr(retry.shutil, "which", lambda _: "terraform")
    monkeypatch.setenv("VIGIE_INFRA_STATE_DIR", str(tmp_path / "state"))
    retry.get_settings.cache_clear()
    monkeypatch.setattr(retry, "run_terraform", FakeTerraform([(0, "Apply complete!")]))
    try:
        assert retry.main(tmp_path) == 0
    finally:
        retry.get_settings.cache_clear()
