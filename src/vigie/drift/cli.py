"""``vigie-drift build-reference``: write the two ``.npy`` files the monitor loads.

The questions come from ``data/golden/questions.jsonl`` and the anchors from the corpus
chunks in ``data/corpus/``. Either one falls back to the drift test fixture while the
real files are missing, and the summary says which source was used.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from vigie.config import Settings
from vigie.drift.embedder import Embedder, FastEmbedEmbedder
from vigie.drift.reference import ReferenceSet
from vigie.drift.sources import load_passages, load_questions


def _parser(settings: Settings) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="vigie-drift")
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build-reference", help="embed golden questions and corpus")
    build.add_argument("--questions", type=Path, help="golden JSONL or drift fixture JSON")
    build.add_argument(
        "--corpus", type=Path, action="append", default=[], help="chunk JSONL file or directory"
    )
    build.add_argument("--reference-out", type=Path, default=settings.drift_reference_path)
    build.add_argument("--anchors-out", type=Path, default=settings.drift_anchors_path)
    build.add_argument("--model", default=settings.dense_model)
    return parser


def _shown(path: Path, root: Path) -> str:
    """Path relative to the working directory when possible, so logs stay portable."""
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def main(
    argv: Sequence[str] | None = None,
    embedder: Embedder | None = None,
    root: Path | None = None,
) -> int:
    settings = Settings()
    args = _parser(settings).parse_args(argv)
    base = root if root is not None else Path.cwd()

    questions, question_source = load_questions(args.questions, base)
    passages, passage_sources = load_passages(args.corpus, base)
    model = embedder if embedder is not None else FastEmbedEmbedder(args.model)
    reference = ReferenceSet.from_texts(
        model,
        questions=questions,
        anchor_texts=[passage.text for passage in passages],
        anchor_groups=[passage.regulation for passage in passages],
    )
    reference_out = base / args.reference_out
    anchors_out = base / args.anchors_out
    reference.save(reference_out, anchors_out)

    print(f"questions: {len(questions)} from {_shown(question_source, base)}")
    sources = ", ".join(_shown(path, base) for path in passage_sources)
    print(f"anchors: {reference.anchors.shape[0]} from {len(passages)} passages in {sources}")
    print(f"wrote {_shown(reference_out, base)} and {_shown(anchors_out, base)}")
    return 0


if __name__ == "__main__":  # pragma: no cover - thin entry point
    raise SystemExit(main())
