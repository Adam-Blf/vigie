"""Keep asking Oracle for an Always Free A1 node until one is free.

Ampere capacity in eu-paris-1 comes and goes, and the region has a single availability
domain, so the only lever is patience. This loop replays `terraform apply` at a gentle
pace and stops on success, on any error that is not a capacity shortage, or after the
seven days the brief allows before switching to the local k3d fallback.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from vigie.config import Settings, get_settings
from vigie.infra.redact import redact

Runner = Callable[[Sequence[str], Path], tuple[int, str]]
Sleeper = Callable[[float], None]

# A 429 is as transient as a capacity shortage; everything else needs a human.
RETRYABLE_MARKERS = ("Out of host capacity", "TooManyRequests")

# Same environment as the manual runs: the OCI tooling cannot read Windows ACLs and would
# warn on every attempt, while the key files are already restricted with icacls.
OCI_QUIET_ENV = {
    "OCI_CLI_SUPPRESS_FILE_PERMISSIONS_WARNING": "True",
    "SUPPRESS_LABEL_WARNING": "True",
}


@dataclass(frozen=True)
class RetryPlan:
    terraform: str
    workdir: Path
    state_path: Path
    log_path: Path
    interval_s: float
    max_attempts: int

    @classmethod
    def from_settings(cls, settings: Settings, terraform: str, root: Path) -> RetryPlan:
        state_dir = settings.infra_state_dir
        return cls(
            terraform=terraform,
            workdir=(root / settings.infra_dir).resolve(),
            state_path=state_dir / "terraform.tfstate",
            log_path=state_dir / "retry.log",
            interval_s=float(settings.infra_retry_interval_s),
            max_attempts=settings.infra_retry_max_attempts,
        )

    def init_cmd(self) -> list[str]:
        # Forward slashes: Terraform on Windows accepts them and they survive any quoting.
        state = self.state_path.as_posix()
        return [
            self.terraform,
            "init",
            "-input=false",
            "-no-color",
            f"-backend-config=path={state}",
        ]

    def apply_cmd(self) -> list[str]:
        return [self.terraform, "apply", "-auto-approve", "-input=false", "-no-color"]


def run_terraform(cmd: Sequence[str], cwd: Path) -> tuple[int, str]:
    env = {**os.environ, **OCI_QUIET_ENV}
    done = subprocess.run(  # noqa: S603 - fixed argument list, no shell
        list(cmd),
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return done.returncode, done.stdout + done.stderr


def is_retryable(output: str) -> bool:
    return any(marker in output for marker in RETRYABLE_MARKERS)


class RetryLog:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, message: str) -> None:
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(f"[{stamp}] {redact(message).rstrip()}\n")


def retry_apply(plan: RetryPlan, runner: Runner, sleep: Sleeper) -> int:
    log = RetryLog(plan.log_path)
    code, output = runner(plan.init_cmd(), plan.workdir)
    if code != 0:
        log.write(f"terraform init failed ({code}), stopping:\n{output}")
        return code

    for attempt in range(1, plan.max_attempts + 1):
        code, output = runner(plan.apply_cmd(), plan.workdir)
        if code == 0:
            log.write(f"attempt {attempt}: apply succeeded\n{output}")
            return 0
        if not is_retryable(output):
            log.write(f"attempt {attempt}: non-capacity error ({code}), stopping:\n{output}")
            return code
        log.write(f"attempt {attempt}/{plan.max_attempts}: no capacity")
        if attempt < plan.max_attempts:
            log.write(f"next try in {plan.interval_s:.0f} s")
            sleep(plan.interval_s)

    log.write("attempts exhausted, switch to the k3d fallback (decision 6)")
    return 1


def main(root: Path) -> int:
    terraform = shutil.which("terraform")
    if terraform is None:
        print("terraform not found on PATH")
        return 2
    settings = get_settings()
    plan = RetryPlan.from_settings(settings, terraform, root)
    if not (plan.workdir / "terraform.tfvars").is_file():
        print(f"missing {plan.workdir / 'terraform.tfvars'}, copy it from ~/.oci/vigie.tfvars")
        return 2
    print(f"retrying terraform apply, log: {plan.log_path}", flush=True)
    return retry_apply(plan, run_terraform, time.sleep)
