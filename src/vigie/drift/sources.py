"""Where the drift reference comes from: golden questions and corpus passages.

The reference is built from files the other milestones produce, read here as plain JSON
so this module does not import their models. Each reader keeps only the fields the
reference needs and ignores the rest, which lets a richer schema land without a change
on this side.

Two fallbacks keep the build usable before those files exist: the drift test fixture
stands in for both the golden set and the corpus.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

GOLDEN_PATH = Path("data/golden/questions.jsonl")
CORPUS_DIR = Path("data/corpus")
FIXTURE_PATH = Path("tests/fixtures/drift_questions.json")


@dataclass(frozen=True)
class Passage:
    regulation: str
    text: str


def _jsonl_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"{path.name} line {line_number}: expected a JSON object")
        rows.append(row)
    return rows


def golden_reference_questions(path: Path) -> list[str]:
    """In-scope, verified, non-test questions of the golden set.

    Out-of-scope and trap questions are not what normal traffic looks like, drafts are
    not reviewed yet, and the sealed test split must never shape anything that is later
    measured on it.
    """
    return [
        str(row["question"])
        for row in _jsonl_rows(path)
        if row.get("category", "in_scope") == "in_scope"
        and row.get("status", "verified") == "verified"
        and row.get("split") != "test"
    ]


def corpus_passages(paths: Iterable[Path]) -> list[Passage]:
    """Every chunk of the corpus JSONL files, reduced to its regulation and text."""
    return [
        Passage(regulation=str(row["regulation"]), text=str(row["text"]))
        for path in sorted(paths)
        for row in _jsonl_rows(path)
    ]


def _fixture(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def fixture_questions(path: Path) -> list[str]:
    return [str(item["text"]) for item in _fixture(path)["reference"]]


def fixture_passages(path: Path) -> list[Passage]:
    return [
        Passage(regulation=str(item["regulation"]), text=str(item["text"]))
        for item in _fixture(path)["corpus_passages"]
    ]


def load_questions(path: Path | None, root: Path) -> tuple[list[str], Path]:
    """Questions from ``path``, else the golden set, else the fixture.

    A ``.jsonl`` file is read as the golden set, anything else as the fixture.
    """
    source = path if path is not None else root / GOLDEN_PATH
    if path is None and not source.is_file():
        source = root / FIXTURE_PATH
    if source.suffix == ".jsonl":
        return golden_reference_questions(source), source
    return fixture_questions(source), source


def load_passages(paths: Sequence[Path], root: Path) -> tuple[list[Passage], list[Path]]:
    """Passages from the given JSONL files or directories, else the corpus, else the fixture."""
    if paths:
        files = sorted(
            file
            for target in paths
            for file in (target.glob("*.jsonl") if target.is_dir() else [target])
        )
        if not files:
            raise FileNotFoundError("no corpus JSONL file in " + ", ".join(map(str, paths)))
        return corpus_passages(files), files
    files = sorted((root / CORPUS_DIR).glob("*.jsonl"))
    if files:
        return corpus_passages(files), files
    fixture = root / FIXTURE_PATH
    return fixture_passages(fixture), [fixture]
