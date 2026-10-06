"""One JSON object per line, one file per regulation: easy to diff, stream and publish."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from vigie.corpus.models import Chunk


def write_chunks(path: Path, chunks: Iterable[Chunk]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for chunk in chunks:
            handle.write(chunk.model_dump_json() + "\n")
            count += 1
    return count


def parse_chunks(text: str) -> list[Chunk]:
    return [Chunk.model_validate_json(line) for line in text.splitlines() if line.strip()]


def read_chunks(path: Path) -> list[Chunk]:
    return parse_chunks(path.read_text(encoding="utf-8"))


def read_corpus_dir(directory: Path) -> list[Chunk]:
    """Every chunk of every regulation, files taken in name order for a stable result."""
    chunks: list[Chunk] = []
    for path in sorted(directory.glob("*.jsonl")):
        chunks.extend(read_chunks(path))
    return chunks
