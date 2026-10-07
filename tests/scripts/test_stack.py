"""scripts/stack.py, behind python tasks.py up and down. Docker is replaced by a recorder."""

from __future__ import annotations

import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest
import stack

LISTING_ACTIVE = "abc123  demo  user  active  created=2026-10-06  expires=2026-11-05  last_used=-\n"


class FakeDocker:
    def __init__(self, listing: str = "", health: str = "healthy", up_code: int = 0) -> None:
        self.listing, self.health, self.up_code = listing, health, up_code
        self.calls: list[tuple[list[str], dict[str, str]]] = []

    def __call__(
        self, cmd: Sequence[str], env: Mapping[str, str], capture: bool
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append((list(cmd), dict(env)))
        out, code = "", 0
        if "ps" in cmd:
            out = self.health
        elif "list" in cmd:
            out = self.listing
        elif "create" in cmd:
            out = "id=x user=demo scope=user\nCopy the token now:\nvig_secret"
        elif "up" in cmd:
            code = self.up_code
        return subprocess.CompletedProcess(list(cmd), code, out, "")

    def commands(self) -> list[str]:
        return [" ".join(cmd) for cmd, _ in self.calls]


@pytest.fixture
def root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / ".env.example").write_text("VIGIE_QDRANT_API_KEY=\nVIGIE_PORT=8710\n")
    monkeypatch.setattr(stack, "ROOT", tmp_path)
    return tmp_path


def test_ensure_env_writes_a_key_once(root: Path) -> None:
    env = root / ".env"
    assert stack.ensure_env(env, root / ".env.example", lambda: "k1") is True
    assert env.read_text() == "VIGIE_QDRANT_API_KEY=k1\nVIGIE_PORT=8710\n"
    assert stack.ensure_env(env, root / ".env.example", lambda: "k2") is False
    assert "k2" not in env.read_text()


def test_ensure_env_appends_a_missing_key(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("VIGIE_PORT=8710")
    assert stack.ensure_env(env, tmp_path / "unused", lambda: "k") is True
    assert env.read_text() == "VIGIE_PORT=8710\nVIGIE_QDRANT_API_KEY=k\n"


def test_up_issues_a_demo_token_once(root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    docker = FakeDocker()
    assert stack.up([], run=docker) == 0
    assert "docker compose up -d --build" in docker.commands()
    assert any("tokens create demo" in c for c in docker.commands())
    printed = capsys.readouterr().out
    assert "vig_secret" in printed
    assert "LLM        fake" in printed
    assert "VIGIE_QDRANT_API_KEY=" in (root / ".env").read_text()

    again = FakeDocker(listing=LISTING_ACTIVE)
    assert stack.up([], run=again) == 0
    assert not any("create" in c for c in again.commands())


def test_local_llm_switches_profile_and_provider(root: Path) -> None:
    docker = FakeDocker(listing=LISTING_ACTIVE)
    assert stack.up(["--local-llm"], run=docker, out=lambda _: None) == 0
    env = docker.calls[0][1]
    assert env["COMPOSE_PROFILES"] == "local-llm"
    assert env["VIGIE_COMPOSE_LLM_PROVIDER"] == "ollama"


def test_up_stops_on_a_failed_start(root: Path) -> None:
    docker = FakeDocker(up_code=3)
    assert stack.up([], run=docker, out=lambda _: None) == 3
    assert len(docker.calls) == 1


def test_up_reports_an_api_that_never_gets_healthy(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(stack, "WAIT_S", 0)
    lines: list[str] = []
    assert stack.up([], run=FakeDocker(health="starting"), out=lines.append) == 1
    assert "not healthy" in lines[-1]


def test_wait_polls_until_healthy(monkeypatch: pytest.MonkeyPatch) -> None:
    states = iter(["starting", "healthy"])
    monkeypatch.setattr(stack.time, "sleep", lambda _: None)

    def run(
        cmd: Sequence[str], env: Mapping[str, str], capture: bool
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(list(cmd), 0, next(states), "")

    assert stack.wait_healthy(run, {}) is True


def test_down_keeps_volumes_unless_asked() -> None:
    docker = FakeDocker()
    assert stack.down([], run=docker) == 0
    assert stack.down(["-v"], run=docker) == 0
    assert docker.commands() == ["docker compose down", "docker compose down --volumes"]
    assert docker.calls[0][1]["COMPOSE_PROFILES"] == "local-llm"


def test_has_demo_token_ignores_revoked_and_other_users() -> None:
    assert stack.has_demo_token(LISTING_ACTIVE)
    assert not stack.has_demo_token(LISTING_ACTIVE.replace("active", "revoked"))
    assert not stack.has_demo_token(LISTING_ACTIVE.replace("demo", "alice"))
