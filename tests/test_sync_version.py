from pathlib import Path

import pytest
from scripts.sync_version import main, read_version, render

README = (
    "# Vigie\n\n"
    "![version](https://img.shields.io/badge/version-0.0.9-001329?style=flat-square)\n\n"
    "Version 0.0.9 - en construction\n"
)


def make_project(tmp_path: Path, version: str, readme: str = README) -> Path:
    (tmp_path / "pyproject.toml").write_text(
        f'[project]\nname = "vigie"\nversion = "{version}"\n', encoding="utf-8"
    )
    (tmp_path / "README.md").write_text(readme, encoding="utf-8")
    return tmp_path


def test_render_updates_line_and_badge() -> None:
    out = render(README, "1.2.3")
    assert "Version 1.2.3 - en construction" in out
    assert "badge/version-1.2.3-001329" in out
    assert "0.0.9" not in out


def test_check_fails_when_readme_is_stale(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = make_project(tmp_path, "0.2.0")
    assert main(["--check"], root) == 1
    assert "out of date" in capsys.readouterr().out
    assert (root / "README.md").read_text(encoding="utf-8") == README


def test_sync_rewrites_then_check_passes(tmp_path: Path) -> None:
    root = make_project(tmp_path, "0.2.0")
    assert main([], root) == 0
    assert "Version 0.2.0" in (root / "README.md").read_text(encoding="utf-8")
    assert main(["--check"], root) == 0


def test_non_string_version_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nversion = 3\n", encoding="utf-8")
    with pytest.raises(TypeError):
        read_version(tmp_path / "pyproject.toml")


def test_repository_readme_is_in_sync() -> None:
    assert main(["--check"]) == 0


def test_package_version_is_synced_too(tmp_path: Path) -> None:
    root = make_project(tmp_path, "0.2.0", readme=README.replace("0.0.9", "0.2.0"))
    init = root / "src" / "vigie" / "__init__.py"
    init.parent.mkdir(parents=True)
    init.write_text('"""Doc."""\n\n__version__ = "0.0.9"\n', encoding="utf-8")
    assert main(["--check"], root) == 1
    assert main([], root) == 0
    assert '__version__ = "0.2.0"' in init.read_text(encoding="utf-8")
    assert main(["--check"], root) == 0
