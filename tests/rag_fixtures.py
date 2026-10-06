"""Shared builders for the LLM and RAG tests."""

from __future__ import annotations

from vigie.rag.labels import eurlex_url
from vigie.rag.types import Passage


def passage(
    article: str = "28",
    paragraph: str | None = "1",
    *,
    regulation: str = "DORA",
    text: str = "Les entités financières gèrent les risques liés aux prestataires tiers. Suite.",
    score: float = 0.9,
) -> Passage:
    return Passage(
        regulation=regulation,
        article=article,
        paragraph=paragraph,
        title="Principes généraux",
        text=text,
        url=eurlex_url(regulation),
        eid=f"{int(article):03d}.{int(paragraph or 0):03d}",
        score=score,
    )


class StubRetriever:
    """Returns a fixed list and remembers what it was asked."""

    def __init__(self, passages: list[Passage]) -> None:
        self.passages = passages
        self.calls: list[tuple[str, int]] = []

    def search(self, question: str, top_k: int) -> list[Passage]:
        self.calls.append((question, top_k))
        return self.passages[:top_k]
