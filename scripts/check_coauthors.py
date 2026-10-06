"""Pair credit gate: every commit of a range must credit Emilien Morice.

Vigie is written by a pair on one machine. Adam's commits carry Emilien as co-author through
the prepare-commit-msg hook, Emilien's commits are his by authorship. A commit made with the
hook disabled, or rewritten by a tool that drops trailers, would erase half of the pair from
the history without anyone noticing, so the CI reads the trailers back instead of trusting
the hook.

Usage: python scripts/check_coauthors.py <base>..<head> [--partner-email EMAIL ...]
Exit codes: 0 every commit credits the partner, 1 at least one does not, 2 git failed.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

# Emilien commits with his GitHub noreply address, his school address may appear in a
# trailer written by hand. Both identify the same person.
DEFAULT_PARTNER_EMAILS = (
    "261297658+emilien754@users.noreply.github.com",
    "emilien.morice@efrei.net",
)

# ASCII unit and record separators cannot appear in a commit message typed by a human, which
# makes them safe delimiters for a single git log call.
FIELD_SEP = "\x1f"
RECORD_SEP = "\x1e"
LOG_FORMAT = f"%H{FIELD_SEP}%an{FIELD_SEP}%ae{FIELD_SEP}%B{RECORD_SEP}"

COAUTHOR_RE = re.compile(r"^co-authored-by:\s*(?P<name>.+?)\s*<(?P<email>[^>]+)>\s*$", re.I)


@dataclass(frozen=True)
class Commit:
    sha: str
    author_name: str
    author_email: str
    message: str


class GitError(RuntimeError):
    """git log could not read the requested range."""


def parse_log(raw: str) -> list[Commit]:
    commits: list[Commit] = []
    for record in raw.split(RECORD_SEP):
        record = record.strip("\n")
        if not record:
            continue
        sha, name, email, message = record.split(FIELD_SEP, 3)
        commits.append(Commit(sha, name, email, message))
    return commits


def coauthor_emails(message: str) -> set[str]:
    emails: set[str] = set()
    for line in message.splitlines():
        match = COAUTHOR_RE.match(line.strip())
        if match:
            emails.add(match.group("email").strip().lower())
    return emails


def credits_partner(commit: Commit, partner_emails: Iterable[str]) -> bool:
    wanted = {email.lower() for email in partner_emails}
    if commit.author_email.lower() in wanted:
        return True
    return bool(coauthor_emails(commit.message) & wanted)


def read_commits(rev_range: str) -> list[Commit]:
    # A range starting with "-" would be read by git as an option, refuse it before calling.
    if rev_range.startswith("-"):
        raise GitError(f"invalid range: {rev_range}")
    result = subprocess.run(  # noqa: S603 - fixed argv, the range is checked above
        ["git", "log", f"--format={LOG_FORMAT}", rev_range],  # noqa: S607 - git from PATH
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if result.returncode != 0:
        raise GitError(result.stderr.strip() or f"git log exited with {result.returncode}")
    return parse_log(result.stdout)


def report(commits: Sequence[Commit], partner_emails: Iterable[str]) -> tuple[list[str], int]:
    lines: list[str] = []
    missing = 0
    wanted = tuple(partner_emails)
    for commit in commits:
        subject = commit.message.splitlines()[0] if commit.message else ""
        ok = credits_partner(commit, wanted)
        missing += not ok
        status = "ok     " if ok else "MISSING"
        lines.append(f"{status} {commit.sha[:12]} {commit.author_name} | {subject}")
    lines.append(f"{len(commits)} commit(s) checked, {missing} without pair credit")
    return lines, missing


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("range", help="git revision range, for example origin/main..HEAD")
    parser.add_argument(
        "--partner-email",
        action="append",
        dest="partner_emails",
        help="address that counts as the partner (repeatable, defaults to Emilien's)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    partner_emails: list[str] = args.partner_emails or list(DEFAULT_PARTNER_EMAILS)
    try:
        commits = read_commits(args.range)
    except GitError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    lines, missing = report(commits, partner_emails)
    print("\n".join(lines))
    if missing:
        print(
            "Every commit needs 'Co-authored-by: Emilien Morice <...>' or Emilien as author. "
            "Reinstall the prepare-commit-msg hook and amend the commits before pushing.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
