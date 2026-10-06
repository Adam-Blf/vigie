"""Print the CHANGELOG section of one version, used as the body of the GitHub release.

The release workflow also calls it with --verify-tag so a tag that disagrees with
pyproject.toml fails before anything is built or published.

Usage: python scripts/release_notes.py 0.2.0
       python scripts/release_notes.py v0.2.0 --verify-tag
"""

from __future__ import annotations

import re
import sys
from collections.abc import Sequence
from pathlib import Path

from scripts.sync_version import ROOT, read_version

HEADING = re.compile(r"^## \[(?P<version>[^\]]+)\]", re.MULTILINE)


class ReleaseError(Exception):
    pass


def section(changelog: str, version: str) -> str:
    headings = list(HEADING.finditer(changelog))
    for index, match in enumerate(headings):
        if match.group("version") != version:
            continue
        end = headings[index + 1].start() if index + 1 < len(headings) else len(changelog)
        body = changelog[match.end() : end].strip()
        # The heading line carries the date after the version, keep only what follows it.
        body = body.split("\n", 1)[1].strip() if "\n" in body else ""
        if not body:
            raise ReleaseError(f"CHANGELOG section for {version} is empty")
        return body
    raise ReleaseError(f"no CHANGELOG section for {version}")


def main(argv: Sequence[str], root: Path = ROOT) -> int:
    if not argv:
        print("usage: release_notes.py <version> [--verify-tag]")
        return 2
    version = argv[0].removeprefix("v")
    try:
        if "--verify-tag" in argv:
            expected = read_version(root / "pyproject.toml")
            if version != expected:
                raise ReleaseError(f"tag v{version} does not match pyproject version {expected}")
        notes = section((root / "CHANGELOG.md").read_text(encoding="utf-8"), version)
    except ReleaseError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(notes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
