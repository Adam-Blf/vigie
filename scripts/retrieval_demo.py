"""Print the hybrid search top-5 for three questions, the visible proof of milestone J2.

Usage: python -m scripts.retrieval_demo                 the three default questions
       python -m scripts.retrieval_demo "question" ...  your own questions

It reads the same settings as the API (VIGIE_QDRANT_URL or VIGIE_QDRANT_PATH), so run
vigie-ingest and vigie-index first.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from typing import TextIO

from vigie.config import Settings, get_settings
from vigie.retrieval.embeddings import Embedder
from vigie.retrieval.factory import open_retriever

TOP = 5
# One question per regulation family, phrased the way a compliance officer asks: the first
# names its article, the two others do not and rely on the meaning.
QUESTIONS = (
    "Que prévoit l'article 28 de DORA sur les prestataires tiers de services TIC ?",
    "Quelles pratiques d'intelligence artificielle sont interdites dans l'Union ?",
    "Dans quel délai une violation de données personnelles doit-elle être notifiée ?",
)
EXCERPT_CHARS = 90


def main(
    argv: Sequence[str],
    out: TextIO = sys.stdout,
    settings: Settings | None = None,
    embedder: Embedder | None = None,
) -> int:
    questions = list(argv) or list(QUESTIONS)
    with open_retriever(settings or get_settings(), embedder=embedder) as retriever:
        for number, question in enumerate(questions, 1):
            out.write(f"\nQ{number}. {question}\n")
            for rank, passage in enumerate(retriever.search(question, TOP), 1):
                excerpt = " ".join(passage.text.split())[:EXCERPT_CHARS]
                out.write(f"  {rank}. {passage.label:<22} rrf={passage.score:.4f}  {excerpt}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
