"""Data shapes that travel between retrieval, the LLM and the API."""

from __future__ import annotations

from dataclasses import dataclass, field

from vigie.rag.labels import article_id, format_label


@dataclass(frozen=True)
class Passage:
    """One retrieved chunk, as the retriever hands it to the RAG layer."""

    regulation: str
    article: str
    paragraph: str | None
    title: str
    text: str
    url: str
    eid: str
    score: float

    @property
    def label(self) -> str:
        return format_label(self.regulation, self.article, self.paragraph)

    @property
    def article_id(self) -> str:
        return article_id(self.regulation, self.article)


@dataclass(frozen=True)
class Citation:
    """A citation that survived validation, ready to be shown with its source link."""

    label: str
    regulation: str
    article: str
    paragraph: str | None
    excerpt: str
    url: str


@dataclass(frozen=True)
class Timings:
    """Milliseconds spent in each stage; first_token_ms is what the user feels."""

    retrieval_ms: float = 0.0
    first_token_ms: float | None = None
    generation_ms: float = 0.0
    total_ms: float = 0.0


@dataclass(frozen=True)
class Answer:
    text: str
    citations: list[Citation]
    sources: list[Passage]
    refused: bool
    trace_id: str
    timings: Timings
    model: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    # Kept for evaluation: labels removed by the validator and the share of raw
    # citations that were valid before filtering (None when the model cited nothing).
    removed_citations: list[str] = field(default_factory=list)
    raw_valid_rate: float | None = None
