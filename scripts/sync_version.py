"""Keep the version shown in the README in step with pyproject.toml.

pyproject.toml is the only place where the version is edited by hand. Everything else is
rewritten from it, so the README can never announce a version the package does not have.

Usage: python scripts/sync_version.py          rewrite the README
       python scripts/sync_version.py --check  fail if the README is out of date
"""

from __future__ import annotations

import re
import sys
from collections.abc import Sequence
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:  # the package still supports 3.10, where tomllib does not exist yet
    import tomli as tomllib

ROOT = Path(__file__).resolve().parent.parent
VERSION_LINE = re.compile(r"^Version \d+\.\d+\.\d+", re.MULTILINE)
VERSION_BADGE = re.compile(r"(img\.shields\.io/badge/version-)\d+\.\d+\.\d+(-)")


def read_version(pyproject: Path) -> str:
    with pyproject.open("rb") as handle:
        version = tomllib.load(handle)["project"]["version"]
    if not isinstance(version, str):
        raise TypeError("project.version must be a string")
    return version


def render(readme: str, version: str) -> str:
    updated = VERSION_LINE.sub(f"Version {version}", readme)
    return VERSION_BADGE.sub(rf"\g<1>{version}\g<2>", updated)


def main(argv: Sequence[str], root: Path = ROOT) -> int:
    version = read_version(root / "pyproject.toml")
    readme_path = root / "README.md"
    current = readme_path.read_text(encoding="utf-8")
    expected = render(current, version)
    if expected == current:
        return 0
    if "--check" in argv:
        print(f"README.md is out of date, run: python scripts/sync_version.py ({version})")
        return 1
    readme_path.write_text(expected, encoding="utf-8")
    print(f"README.md set to version {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
