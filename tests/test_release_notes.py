from pathlib import Path

import pytest
from scripts.release_notes import ReleaseError, main, section

CHANGELOG = """# Changelog

## [Unreleased]

## [0.2.0] - 2026-10-03

### Added

- corpus EUR-Lex

## [0.1.0] - 2026-10-02

### Added

- squelette
"""


def make_project(tmp_path: Path, version: str) -> Path:
    (tmp_path / "pyproject.toml").write_text(
        f'[project]\nname = "vigie"\nversion = "{version}"\n', encoding="utf-8"
    )
    (tmp_path / "CHANGELOG.md").write_text(CHANGELOG, encoding="utf-8")
    return tmp_path


def test_section_returns_only_the_requested_version() -> None:
    notes = section(CHANGELOG, "0.2.0")
    assert "corpus EUR-Lex" in notes
    assert "squelette" not in notes
    assert "## [" not in notes


def test_last_section_reads_to_end_of_file() -> None:
    assert section(CHANGELOG, "0.1.0").endswith("- squelette")


def test_missing_or_empty_section_raises() -> None:
    with pytest.raises(ReleaseError, match="no CHANGELOG section"):
        section(CHANGELOG, "9.9.9")
    with pytest.raises(ReleaseError, match="empty"):
        section(CHANGELOG, "Unreleased")


def test_verify_tag_rejects_a_mismatch(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = make_project(tmp_path, "0.2.0")
    assert main(["v0.1.0", "--verify-tag"], root) == 1
    assert "does not match" in capsys.readouterr().err


def test_verify_tag_prints_notes_on_match(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = make_project(tmp_path, "0.2.0")
    assert main(["v0.2.0", "--verify-tag"], root) == 0
    assert "corpus EUR-Lex" in capsys.readouterr().out


def test_usage_without_arguments() -> None:
    assert main([]) == 2


def test_repository_changelog_has_current_version() -> None:
    assert main(["v0.1.0", "--verify-tag"]) == 0
