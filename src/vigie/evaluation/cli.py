"""``vigie-eval`` console script.

Subcommands:
  validate-golden  check the golden set against the corpus and its seal, exit 1 on any issue
  seal-golden      write data/golden/test.sha256 from the current test rows
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from vigie.config import get_settings
from vigie.evaluation.corpus_text import load_corpus
from vigie.evaluation.golden import load_golden, read_seal, sealed_digest, write_seal
from vigie.evaluation.validate import Report, validate_golden


def _print_report(report: Report, total: int) -> None:
    print(f"questions: {total}")
    for dimension, counter in report.counts.items():
        cells = ", ".join(f"{key}={counter[key]}" for key in sorted(counter))
        print(f"  by {dimension}: {cells}")
    if report.ok:
        print("golden set OK")
        return
    print(f"{len(report.issues)} issue(s):")
    for issue in report.issues:
        print(f"  {issue}")


def _validate(args: argparse.Namespace) -> int:
    questions = load_golden(args.golden)
    corpus = load_corpus(args.corpus)
    seal = read_seal(args.seal) if args.seal.exists() else None
    report = validate_golden(questions, corpus, seal)
    print(f"corpus: {len(corpus)} articles read from {args.corpus}")
    _print_report(report, len(questions))
    return 0 if report.ok else 1


def _seal(args: argparse.Namespace) -> int:
    questions = load_golden(args.golden)
    if any(q.split is None for q in questions):
        print("every row needs a split before sealing", file=sys.stderr)
        return 1
    # Resealing is how the test split gets changed on purpose. Requiring --force keeps it
    # from happening as a side effect of a script that only meant to refresh the file.
    if args.seal.exists() and read_seal(args.seal) != sealed_digest(questions) and not args.force:
        print("the test split changed since it was sealed, pass --force to reseal", file=sys.stderr)
        return 1
    print(write_seal(args.seal, questions))
    return 0


def build_parser() -> argparse.ArgumentParser:
    settings = get_settings()
    parser = argparse.ArgumentParser(prog="vigie-eval", description="Vigie evaluation tools")
    commands = parser.add_subparsers(dest="command", required=True)

    def golden_args(sub: argparse.ArgumentParser) -> None:
        sub.add_argument("--golden", type=Path, default=settings.golden_path)
        sub.add_argument("--seal", type=Path, default=settings.golden_seal_path)

    validate = commands.add_parser("validate-golden", help="check the golden set")
    golden_args(validate)
    validate.add_argument(
        "--corpus",
        type=Path,
        default=settings.corpus_dir,
        help="directory of chunk JSONL files, or of Cellar XHTML files named <CELEX>.xhtml",
    )
    validate.set_defaults(handler=_validate)

    seal = commands.add_parser("seal-golden", help="write the test split seal")
    golden_args(seal)
    seal.add_argument("--force", action="store_true", help="overwrite a different seal")
    seal.set_defaults(handler=_seal)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    code: int = args.handler(args)
    return code


if __name__ == "__main__":  # pragma: no cover - exercised through the console script
    raise SystemExit(main())
