"""Keep every copy of the version in step with pyproject.toml.

pyproject.toml is the only place where the version is edited by hand. The README and the
package's __version__ are rewritten from it, so neither the README nor the API (which
reports __version__ in every answer, for the canary) can announce a version the package
does not have.

Usage: python scripts/sync_version.py          rewrite the copies
       python scripts/sync_version.py --check  fail if a copy is out of date
"""

from __future__ import annotations

import re
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:  # the package still supports 3.10, where tomllib does not exist yet
    import tomli as tomllib

ROOT = Path(__file__).resolve().parent.parent
VERSION_LINE = re.compile(r"^Version \d+\.\d+\.\d+", re.MULTILINE)
VERSION_BADGE = re.compile(r"(img\.shields\.io/badge/version-)\d+\.\d+\.\d+(-)")
DUNDER_VERSION = re.compile(r'^__version__ = "[^"]*"', re.MULTILINE)
PACKAGE_INIT = Path("src/vigie/__init__.py")


def read_version(pyproject: Path) -> str:
    with pyproject.open("rb") as handle:
        version = tomllib.load(handle)["project"]["version"]
    if not isinstance(version, str):
        raise TypeError("project.version must be a string")
    return version


def render(readme: str, version: str) -> str:
    updated = VERSION_LINE.sub(f"Version {version}", readme)
    return VERSION_BADGE.sub(rf"\g<1>{version}\g<2>", updated)


def render_init(source: str, version: str) -> str:
    return DUNDER_VERSION.sub(f'__version__ = "{version}"', source)


def main(argv: Sequence[str], root: Path = ROOT) -> int:
    version = read_version(root / "pyproject.toml")
    targets: list[tuple[Path, Callable[[str, str], str]]] = [(root / "README.md", render)]
    if (root / PACKAGE_INIT).exists():
        targets.append((root / PACKAGE_INIT, render_init))
    stale = []
    for path, rewrite in targets:
        current = path.read_text(encoding="utf-8")
        expected = rewrite(current, version)
        if expected != current:
            stale.append((path, expected))
    if not stale:
        return 0
    names = ", ".join(path.relative_to(root).as_posix() for path, _ in stale)
    if "--check" in argv:
        print(f"{names} out of date, run: python scripts/sync_version.py ({version})")
        return 1
    for path, expected in stale:
        path.write_text(expected, encoding="utf-8")
    print(f"{names} set to version {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
