"""Start and stop the Docker Compose stack, behind `python tasks.py up` and `down`.

    python tasks.py up [--local-llm]    build, start, wait for the API, print a demo token once
    python tasks.py down [-v]           stop; -v also deletes the volumes

The first run writes a random Qdrant API key into .env (created from .env.example when
missing). The key is never printed: Qdrant and the API read it from there.

The demo token is issued inside the API container, printed once on the terminal and never
written anywhere else; only its hash lands in the API database. A later `up` finds the
active demo token and leaves it alone.
"""

from __future__ import annotations

import os
import re
import secrets
import shutil
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KEY = "VIGIE_QDRANT_API_KEY"
DEMO_USER = "demo"
WAIT_S = 900
URLS = (
    ("interface", "http://127.0.0.1:4710"),
    ("API", "http://127.0.0.1:8710/healthz"),
    ("MLflow", "http://127.0.0.1:5710"),
)

# (command, environment, capture output) -> finished process
Runner = Callable[[Sequence[str], Mapping[str, str], bool], "subprocess.CompletedProcess[str]"]


def ensure_env(env_file: Path, example: Path, make_key: Callable[[], str]) -> bool:
    """Make sure env_file holds a non-empty Qdrant key; True when a key was written."""
    if not env_file.exists():
        shutil.copyfile(example, env_file)
    text = env_file.read_text(encoding="utf-8")
    pattern = re.compile(rf"^{KEY}=(.*)$", re.MULTILINE)
    match = pattern.search(text)
    if match and match.group(1).strip():
        return False
    line = f"{KEY}={make_key()}"
    if match:
        text = pattern.sub(line, text, count=1)
    else:
        text = text + ("" if text.endswith("\n") or not text else "\n") + line + "\n"
    env_file.write_text(text, encoding="utf-8")
    return True


def compose_env(local_llm: bool, base: Mapping[str, str]) -> dict[str, str]:
    """The environment of the compose commands: the local-llm profile switches the LLM."""
    env = dict(base)
    if local_llm:
        env["COMPOSE_PROFILES"] = "local-llm"
        env["VIGIE_COMPOSE_LLM_PROVIDER"] = "ollama"
    return env


def has_demo_token(listing: str) -> bool:
    return any(
        len(cols) >= 4 and cols[1] == DEMO_USER and cols[3] == "active"
        for cols in (line.split() for line in listing.splitlines())
    )


def _run(
    cmd: Sequence[str], env: Mapping[str, str], capture: bool
) -> subprocess.CompletedProcess[str]:
    # Fixed argument lists, no shell: nothing from outside reaches a command line.
    return subprocess.run(  # noqa: S603
        list(cmd), cwd=ROOT, env=dict(env), text=True, capture_output=capture, check=False
    )


def _compose(*args: str) -> list[str]:
    return ["docker", "compose", *args]


def wait_healthy(run: Runner, env: Mapping[str, str], timeout_s: float | None = None) -> bool:
    deadline = time.monotonic() + (WAIT_S if timeout_s is None else timeout_s)
    while time.monotonic() < deadline:
        status = run(_compose("ps", "api", "--format", "{{.Health}}"), env, True).stdout.strip()
        if status == "healthy":
            return True
        time.sleep(5)
    return False


def up(args: Sequence[str], run: Runner = _run, out: Callable[[str], None] = print) -> int:
    local_llm = "--local-llm" in args
    if ensure_env(ROOT / ".env", ROOT / ".env.example", lambda: secrets.token_urlsafe(32)):
        out(f"wrote a random {KEY} into .env")
    env = compose_env(local_llm, os.environ)
    out("building and starting the stack, the first run takes several minutes")
    # Not captured: the build and the ingestion are long, their progress belongs on screen.
    started = run(_compose("up", "-d", "--build"), env, False)
    if started.returncode != 0:
        return started.returncode
    if not wait_healthy(run, env):
        out("the API is not healthy, see: docker compose logs ingest api")
        return 1
    listing = run(
        _compose("exec", "-T", "api", "python", "-m", "vigie.api.tokens", "list"), env, True
    )
    if has_demo_token(listing.stdout):
        out("a demo token is already active; issue another with:")
        out("  docker compose exec api python -m vigie.api.tokens create <user>")
    else:
        create = ("python", "-m", "vigie.api.tokens", "create", DEMO_USER)
        issued = run(_compose("exec", "-T", "api", *create), env, True)
        out(issued.stdout.strip())
    for name, url in URLS:
        out(f"{name:<10} {url}")
    out(f"LLM        {'ollama (local-llm profile)' if local_llm else 'fake'}")
    return 0


def down(args: Sequence[str], run: Runner = _run, out: Callable[[str], None] = print) -> int:
    volumes = ["--volumes"] if "-v" in args or "--volumes" in args else []
    # Every profile, so a stack started with --local-llm stops entirely.
    env = compose_env(True, os.environ)
    return run(_compose("down", *volumes), env, False).returncode


if __name__ == "__main__":  # pragma: no cover - tasks.py is the entry point
    raise SystemExit(up(sys.argv[1:]))
