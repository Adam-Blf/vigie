"""Project task runner. Plain Python so it works the same on Windows and Linux, no .bat or .ps1.

Usage: python tasks.py <task> [args...]
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TASKS: dict[str, Callable[[Sequence[str]], int]] = {}


def task(fn: Callable[[Sequence[str]], int]) -> Callable[[Sequence[str]], int]:
    TASKS[fn.__name__.replace("_", "-")] = fn
    return fn


def run(cmd: Sequence[str]) -> int:
    print("+", " ".join(cmd), flush=True)
    return subprocess.call(list(cmd), cwd=ROOT)  # noqa: S603 - commands are fixed lists


def py(*args: str) -> list[str]:
    return [sys.executable, "-m", *args]


@task
def lint(_: Sequence[str]) -> int:
    return run(py("ruff", "check", ".")) or run(py("ruff", "format", "--check", "."))


@task
def typecheck(_: Sequence[str]) -> int:
    return run(py("mypy", "src"))


@task
def test(args: Sequence[str]) -> int:
    return run(py("pytest", "--cov=src", "--cov-report=term-missing", *args))


@task
def check(args: Sequence[str]) -> int:
    for step in (lint, typecheck, test):
        code = step(args if step is test else [])
        if code:
            return code
    return 0


# The project bans these characters everywhere. The dashes and the middle dot are a house
# style rule; the invisible ones are worse, they silently break grep, slugs and links.
# Code points rather than literals: writing them in the source would make this file fail
# its own check, and an invisible literal is impossible to review anyway.
FORBIDDEN_CHARS: dict[str, str] = {
    chr(code): f"{name} U+{code:04X}"
    for code, name in (
        (0x2014, "em dash"),
        (0x2013, "en dash"),
        (0x00B7, "middle dot"),
        (0x200B, "zero width space"),
        (0x200C, "zero width non-joiner"),
        (0x200D, "zero width joiner"),
        (0x2060, "word joiner"),
        (0xFEFF, "byte order mark"),
        (0x200E, "left-to-right mark"),
        (0x200F, "right-to-left mark"),
        (0x202A, "bidi embedding"),
        (0x202B, "bidi embedding"),
        (0x202C, "bidi pop"),
        (0x202D, "bidi override"),
        (0x202E, "bidi override"),
        (0x2066, "bidi isolate"),
        (0x2067, "bidi isolate"),
        (0x2068, "bidi isolate"),
        (0x2069, "bidi pop isolate"),
    )
}


def find_forbidden(text: str) -> list[tuple[int, int, str]]:
    """Return (line, column, name) for every banned character, both counted from 1."""
    hits = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for col, char in enumerate(line, start=1):
            name = FORBIDDEN_CHARS.get(char)
            if name:
                hits.append((lineno, col, name))
    return hits


def repo_files() -> list[Path]:
    # Untracked files count too, otherwise a new document escapes the check until it is
    # committed, which is exactly when it is too late.
    listing = subprocess.run(  # noqa: S603 - fixed argument list, no user input
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],  # noqa: S607
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [ROOT / line for line in listing.splitlines() if line]


@task
def typo(args: Sequence[str]) -> int:
    files = [ROOT / arg for arg in args] if args else repo_files()
    found = 0
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError, IsADirectoryError):
            continue  # binary or removed files carry no prose
        shown = path.relative_to(ROOT) if path.is_relative_to(ROOT) else path
        for lineno, col, name in find_forbidden(text):
            print(f"{shown.as_posix()}:{lineno}:{col}: {name}")
            found += 1
    print(f"typo: {len(files)} files scanned, {found} forbidden characters")
    return 1 if found else 0


def main(argv: Sequence[str]) -> int:
    if not argv or argv[0] not in TASKS:
        print("tasks:", ", ".join(sorted(TASKS)))
        return 2
    return TASKS[argv[0]](argv[1:])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
