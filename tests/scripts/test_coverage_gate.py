from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import coverage_gate as cg
import pytest


def _summary(lines: int, covered: int, branches: int = 0, covered_branches: int = 0) -> Any:
    return {
        "summary": {
            "num_statements": lines,
            "covered_lines": covered,
            "num_branches": branches,
            "covered_branches": covered_branches,
        }
    }


REPORT: dict[str, Any] = {
    "files": {
        "src\\vigie\\drift\\detector.py": _summary(90, 90, 10, 10),
        "src/vigie/drift/window.py": _summary(10, 2),
        "src/vigie/api/auth.py": _summary(20, 20),
        "src/vigie/api/authz.py": _summary(20, 0),
        "src/vigie/config.py": _summary(40, 40),
    }
}


def test_tally_of_empty_module_counts_as_full() -> None:
    assert cg.Tally(0, 0).percent == 100.0


def test_normalize_handles_windows_and_dot_prefix() -> None:
    assert cg.normalize(".\\src\\vigie\\x.py") == "src/vigie/x.py"
    assert cg.normalize("./src/a.py") == "src/a.py"


def test_parse_floor_accepts_prefix_and_percent() -> None:
    assert cg.parse_floor("src/vigie/drift/=95") == cg.Floor("src/vigie/drift", 95.0)


@pytest.mark.parametrize("spec", ["95", "=95", "src=abc", "src=101", "src=-1"])
def test_parse_floor_rejects_bad_specs(spec: str) -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        cg.parse_floor(spec)


def test_matches_respects_module_boundaries() -> None:
    assert cg.matches("src/vigie/api/auth.py", "src/vigie/api/auth")
    assert cg.matches("src/vigie/api/auth/tokens.py", "src/vigie/api/auth")
    assert cg.matches("src/vigie/rag/citations.py", "src/vigie/rag/citations.py")
    assert not cg.matches("src/vigie/api/authz.py", "src/vigie/api/auth")


def test_tally_under_sums_lines_and_branches() -> None:
    files = cg.load_files(REPORT)
    tally = cg.tally_under(files, "src/vigie/drift")
    assert tally == cg.Tally(102, 110)
    assert cg.tally_under(files, "src/vigie/guard") is None


def test_load_files_rejects_foreign_json() -> None:
    with pytest.raises(cg.ReportError):
        cg.load_files({"totals": {}})


def test_evaluate_flags_module_below_its_floor() -> None:
    files = cg.load_files(REPORT)
    floors = [cg.Floor("src/vigie/drift", 95.0), cg.Floor("src/vigie/api/auth", 95.0)]
    lines, passed = cg.evaluate(files, 50.0, floors)
    assert not passed
    assert any(line.startswith("FAIL src/vigie/drift") for line in lines)
    assert any(line.startswith("ok   src/vigie/api/auth 100.0%") for line in lines)


def test_evaluate_reports_absent_module_without_failing() -> None:
    files = cg.load_files(REPORT)
    lines, passed = cg.evaluate(files, 0.0, [cg.Floor("src/vigie/guard", 95.0)])
    assert passed
    assert lines[-1].startswith("absent src/vigie/guard")


def test_evaluate_fails_on_total_floor() -> None:
    files = cg.load_files(REPORT)
    lines, passed = cg.evaluate(files, 99.0, [])
    assert not passed
    assert lines[0].startswith("FAIL total")


def _write(tmp_path: Path, payload: object) -> Path:
    path = tmp_path / "coverage.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_main_exit_codes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = _write(tmp_path, REPORT)
    assert cg.main([str(path), "--total", "50", "--path", "src/vigie/api/auth=95"]) == 0
    assert cg.main([str(path), "--path", "src/vigie/drift=99"]) == 1
    assert "FAIL src/vigie/drift" in capsys.readouterr().out


@pytest.mark.parametrize("payload", [[1, 2], {"files": []}])
def test_main_rejects_unreadable_report(
    tmp_path: Path, payload: object, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cg.main([str(_write(tmp_path, payload))]) == 2
    assert capsys.readouterr().err.startswith("error:")


def test_main_rejects_missing_file(tmp_path: Path) -> None:
    assert cg.main([str(tmp_path / "missing.json")]) == 2
