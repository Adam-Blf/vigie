"""Coverage floors per module, read from the JSON report of coverage.py.

pytest-cov only knows one global floor. The brief asks for more on the code where a silent
bug costs the most (guardrails, citation filter, auth, usage, drift), so this script sums
lines and branches under each path prefix and compares them to their own floor.

A prefix with no measured file is reported as absent and does not fail: the module simply
does not exist yet on this branch. As soon as it lands, its floor applies.

Usage: python scripts/coverage_gate.py coverage.json --total 80 --path src/vigie/drift=95
Exit codes: 0 every floor holds, 1 at least one floor is missed, 2 unreadable report or args.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Tally:
    covered: int
    total: int

    @property
    def percent(self) -> float:
        # Nothing to execute means nothing left untested, the same convention as coverage.py.
        return 100.0 if self.total == 0 else 100.0 * self.covered / self.total


@dataclass(frozen=True)
class Floor:
    prefix: str
    minimum: float


class ReportError(ValueError):
    """The file is not a coverage.py JSON report."""


def normalize(path: str) -> str:
    # coverage.py writes native separators, so the same report differs between Windows and CI.
    return path.replace("\\", "/").removeprefix("./")


def parse_floor(spec: str) -> Floor:
    prefix, sep, value = spec.rpartition("=")
    if not sep or not prefix:
        raise argparse.ArgumentTypeError(f"expected PREFIX=PERCENT, got {spec!r}")
    try:
        minimum = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"not a percentage: {value!r}") from exc
    if not 0.0 <= minimum <= 100.0:
        raise argparse.ArgumentTypeError(f"percentage out of range: {value!r}")
    return Floor(normalize(prefix).rstrip("/"), minimum)


def file_tally(summary: Mapping[str, Any]) -> Tally:
    covered = int(summary.get("covered_lines", 0)) + int(summary.get("covered_branches", 0))
    total = int(summary.get("num_statements", 0)) + int(summary.get("num_branches", 0))
    return Tally(covered, total)


def load_files(report: Mapping[str, Any]) -> dict[str, Tally]:
    files = report.get("files")
    if not isinstance(files, Mapping):
        raise ReportError("no 'files' table, is this a coverage.py JSON report?")
    return {normalize(path): file_tally(entry.get("summary", {})) for path, entry in files.items()}


def matches(path: str, prefix: str) -> bool:
    # "src/vigie/api/auth" must cover auth.py and an auth/ package, but not authz.py.
    return path in (prefix, f"{prefix}.py") or path.startswith(f"{prefix}/")


def tally_under(files: Mapping[str, Tally], prefix: str) -> Tally | None:
    selected = [tally for path, tally in files.items() if matches(path, prefix)]
    if not selected:
        return None
    return Tally(sum(t.covered for t in selected), sum(t.total for t in selected))


def evaluate(
    files: Mapping[str, Tally], total_floor: float, floors: Sequence[Floor]
) -> tuple[list[str], bool]:
    lines: list[str] = []
    passed = True
    overall = Tally(sum(t.covered for t in files.values()), sum(t.total for t in files.values()))
    ok = overall.percent >= total_floor
    passed &= ok
    lines.append(f"{'ok  ' if ok else 'FAIL'} total {overall.percent:.1f}% (floor {total_floor}%)")
    for floor in floors:
        tally = tally_under(files, floor.prefix)
        if tally is None:
            lines.append(f"absent {floor.prefix} (floor {floor.minimum}% applies once it exists)")
            continue
        ok = tally.percent >= floor.minimum
        passed &= ok
        lines.append(
            f"{'ok  ' if ok else 'FAIL'} {floor.prefix} {tally.percent:.1f}% "
            f"(floor {floor.minimum}%)"
        )
    return lines, passed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("report", type=Path, help="coverage.py JSON report")
    parser.add_argument("--total", type=float, default=0.0, help="floor for the whole report")
    parser.add_argument(
        "--path", type=parse_floor, action="append", default=[], help="PREFIX=PERCENT"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = json.loads(args.report.read_text(encoding="utf-8"))
        if not isinstance(report, Mapping):
            raise ReportError("top level is not an object")
        files = load_files(report)
    except (OSError, json.JSONDecodeError, ReportError) as exc:
        print(f"error: cannot read {args.report}: {exc}", file=sys.stderr)
        return 2
    lines, passed = evaluate(files, args.total, args.path)
    print("\n".join(lines))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
