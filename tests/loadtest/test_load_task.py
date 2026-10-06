import importlib.util
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType

import pytest

from vigie.config import get_settings

ROOT = Path(__file__).resolve().parents[2]


def _tasks_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("vigie_tasks", ROOT / "tasks.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_load_local_runs_the_local_protocol(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    tasks = _tasks_module()
    captured: list[Sequence[str]] = []
    monkeypatch.setattr(tasks, "ROOT", tmp_path)
    monkeypatch.setattr(tasks, "run", lambda cmd: captured.append(cmd) or 0)
    monkeypatch.setenv("VIGIE_PORT", "8711")
    get_settings.cache_clear()
    try:
        assert tasks.main(["load-local", "-t", "30s"]) == 0
    finally:
        get_settings.cache_clear()

    (cmd,) = captured
    joined = " ".join(cmd)
    assert "locust -f load/locustfile.py --headless -u 20 -r 4 -t 5m" in joined
    assert "--host http://127.0.0.1:8711" in joined
    # Extra arguments come last so Locust lets them override the defaults.
    assert list(cmd[-2:]) == ["-t", "30s"]
    assert (tmp_path / "results" / "load").is_dir()
