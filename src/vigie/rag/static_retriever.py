"""A retriever over a fixed list of passages read from a JSON file.

It ignores the question and returns the best scored passages. That is exactly what is
needed to measure the model alone, with hand-picked passages, while the real index is
still being built, and it keeps the measurement free of retrieval noise.
"""

from __future__ import annotations

import json
from pathlib import Path

from vigie.rag.types import Passage


class StaticRetriever:
    def __init__(self, passages: list[Passage]) -> None:
        self._passages = sorted(passages, key=lambda p: p.score, reverse=True)

    @classmethod
    def from_json(cls, path: Path) -> StaticRetriever:
        rows = json.loads(path.read_text(encoding="utf-8"))
        return cls([Passage(**row) for row in rows])

    def search(self, question: str, top_k: int) -> list[Passage]:
        return self._passages[:top_k]
