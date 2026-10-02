"""Project task runner. Plain Python so it works the same on Windows and Linux, no .bat or .ps1.

Usage: python tasks.py <task> [args...]
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TASKS: dict[str, Callable[[Sequence[str]], int]] = {}


def task(fn: Callable[[Sequence[str]], int]) -> Callable[[Sequence[str]], int]:
    TASKS[fn.__name__.replace("_", "-")] = fn
    return fn


def run(cmd: Sequence[str]) -> int:
    print("+", " ".join(cmd), flush=True)
    return subprocess.call(list(cmd), cwd=ROOT)  # noqa: S603 - commands are fixed lists


def py(*args: str) -> list[str]:
    return [sys.executable, "-m", *args]


@task
def lint(_: Sequence[str]) -> int:
    return run(py("ruff", "check", ".")) or run(py("ruff", "format", "--check", "."))


@task
def typecheck(_: Sequence[str]) -> int:
    return run(py("mypy", "src"))


@task
def test(args: Sequence[str]) -> int:
    return run(py("pytest", "--cov=src", "--cov-report=term-missing", *args))


@task
def check(args: Sequence[str]) -> int:
    for step in (lint, typecheck, test):
        code = step(args if step is test else [])
        if code:
            return code
    return 0


@task
def redteam(args: Sequence[str]) -> int:
    # Replays redteam/attacks.generated.yaml against the API named by VIGIE_REDTEAM_BASE_URL,
    # then lets score.py decide. promptfoo exits 100 as soon as one attack gets through, which
    # is expected below the 5 % gate, so only other codes stop the task here.
    bin_dir = ROOT / "redteam" / "node_modules" / ".bin"
    promptfoo = shutil.which("promptfoo", path=str(bin_dir))
    if promptfoo is None:
        print("promptfoo missing: run `npm ci` in redteam/ first", file=sys.stderr)
        return 2
    results = "redteam/results.json"
    replay = [promptfoo, "eval", "-c", "redteam/replay.yaml", "-o", results]
    code = run([*replay, "--no-cache", "--no-share"])
    if code not in (0, 100):
        return code
    return run([sys.executable, "redteam/score.py", results, *args])


def main(argv: Sequence[str]) -> int:
    if not argv or argv[0] not in TASKS:
        print("tasks:", ", ".join(sorted(TASKS)))
        return 2
    return TASKS[argv[0]](argv[1:])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
