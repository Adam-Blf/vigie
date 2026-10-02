"""The typography check is a gate, so it has to be seen failing on a bad file."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]

EM_DASH = chr(0x2014)
EN_DASH = chr(0x2013)
MIDDLE_DOT = chr(0x00B7)
ZERO_WIDTH_SPACE = chr(0x200B)
# French typography needs these, the cleanup must leave them alone.
NO_BREAK_SPACE = chr(0x00A0)
NARROW_NO_BREAK_SPACE = chr(0x202F)


@pytest.fixture(scope="module")
def tasks() -> ModuleType:
    # tasks.py sits at the repository root, outside any package, so load it by path.
    spec = importlib.util.spec_from_file_location("tasks", ROOT / "tasks.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("char", [EM_DASH, EN_DASH, MIDDLE_DOT, ZERO_WIDTH_SPACE])
def test_find_forbidden_reports_position(tasks: ModuleType, char: str) -> None:
    hits = tasks.find_forbidden(f"ok\nab{char}c")
    assert [(line, col) for line, col, _ in hits] == [(2, 3)]


def test_find_forbidden_keeps_french_spaces(tasks: ModuleType) -> None:
    text = f"Article 28{NO_BREAK_SPACE}:{NARROW_NO_BREAK_SPACE}sous-traitance."
    assert tasks.find_forbidden(text) == []


def test_typo_task_fails_on_bad_file(
    tasks: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bad = tmp_path / "bad.md"
    bad.write_text(f"DORA {EM_DASH} article 28\n", encoding="utf-8")
    assert tasks.typo([str(bad)]) == 1
    assert "em dash U+2014" in capsys.readouterr().out


def test_typo_task_passes_on_clean_file(tasks: ModuleType, tmp_path: Path) -> None:
    good = tmp_path / "good.md"
    good.write_text("DORA, article 28 - sous-traitance.\n", encoding="utf-8")
    assert tasks.typo([str(good)]) == 0


def test_typo_task_skips_binary_files(tasks: ModuleType, tmp_path: Path) -> None:
    blob = tmp_path / "blob.bin"
    blob.write_bytes(b"\xff\xfe\x00\x80")
    assert tasks.typo([str(blob)]) == 0
