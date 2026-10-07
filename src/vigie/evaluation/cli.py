"""``vigie-eval`` console script.

Subcommands:
  validate-golden  check the golden set against the corpus and its seal, exit 1 on any issue
  seal-golden      write data/golden/test.sha256 from the current test rows
  retrieval        recall@k and MRR of the configured retriever on one split (dev by default)
  run, gate, register, alias
                   the evaluation loop with MLflow and the registry, see run_cli.py
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from vigie.config import get_settings
from vigie.evaluation.corpus_text import load_corpus
from vigie.evaluation.golden import load_golden, read_seal, sealed_digest, write_seal
from vigie.evaluation.retrieval_eval import evaluate_retrieval
from vigie.evaluation.run_cli import add_commands
from vigie.evaluation.validate import Report, validate_golden
from vigie.retrieval.factory import open_retriever


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


def _retrieval(args: argparse.Namespace) -> int:
    questions = load_golden(args.golden)
    with open_retriever(get_settings()) as retriever:
        result = evaluate_retrieval(
            questions, retriever, split=args.split, k=args.k, depth=args.depth
        )
    for row in result.rows:
        top = ", ".join(row.retrieved[: args.k])
        print(f"{row.id:<10} rr={row.reciprocal_rank:.3f} expected={','.join(row.expected)}  {top}")
    print(
        f"split={result.split} questions={result.questions} k={result.k} depth={result.depth} "
        f"recall@{result.k}={result.recall_at_k:.4f} mrr={result.mrr:.4f}"
    )
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(result.as_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
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

    retrieval = commands.add_parser("retrieval", help="recall@k and MRR of the retriever")
    golden_args(retrieval)
    # dev by default: the test split is sealed for the published figures and must never be
    # the one a setting is tuned on.
    retrieval.add_argument("--split", choices=["dev", "test"], default="dev")
    retrieval.add_argument("--k", type=int, default=5)
    retrieval.add_argument("--depth", type=int, default=20, help="passages asked per question")
    retrieval.add_argument("--out", type=Path, help="also write the result as JSON")
    retrieval.set_defaults(handler=_retrieval)
    add_commands(commands, settings)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    code: int = args.handler(args)
    return code


if __name__ == "__main__":  # pragma: no cover - exercised through the console script
    raise SystemExit(main())
