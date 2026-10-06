"""A mini corpus and a deterministic embedder, so retrieval tests never touch the network.

The fake embedder hashes words into buckets: two texts sharing words get close vectors,
which is all the ranking tests need. RGPD article 28 is in the corpus on purpose, a
question about "article 28 DORA" has to beat it on the regulation name.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

from vigie.config import Settings
from vigie.corpus.jsonl import read_corpus_dir, write_chunks
from vigie.corpus.models import Chunk
from vigie.retrieval.client import open_client
from vigie.retrieval.embeddings import Embedded, SparseVector
from vigie.retrieval.index import build_index

DIM = 64


def chunk(regulation: str, article: str, paragraph: str | None, title: str, text: str) -> Chunk:
    eid = f"art_{article}" + (f".par_{paragraph}" if paragraph else "")
    return Chunk(
        regulation=regulation,
        celex="32022R2554" if regulation == "DORA" else "32016R0679",
        kind="article",
        article=article,
        paragraph=paragraph,
        title=title,
        chapter="CHAPITRE V",
        text=text,
        url=f"https://eur-lex.europa.eu/legal-content/FR/TXT/?uri=CELEX:x#{eid}",
        eid=eid,
        retrieved_on="2026-10-02",
    )


MINI_CORPUS: tuple[Chunk, ...] = (
    chunk(
        "DORA",
        "28",
        "1",
        "Principes généraux",
        "Les entités financières gèrent les risques liés aux prestataires tiers de services TIC.",
    ),
    chunk(
        "DORA",
        "30",
        None,
        "Principales dispositions contractuelles",
        "Les droits et obligations de l'entité financière et du prestataire sont écrits.",
    ),
    chunk(
        "DORA",
        "5",
        None,
        "Gouvernance et organisation",
        "L'organe de direction assume la responsabilité ultime de la gestion du risque TIC.",
    ),
    chunk(
        "RGPD",
        "28",
        None,
        "Sous-traitant",
        "Le responsable du traitement fait appel à des sous-traitants présentant des garanties.",
    ),
    chunk(
        "RGPD",
        "33",
        None,
        "Notification à l'autorité de contrôle d'une violation de données",
        "La violation est notifiée dans les meilleurs délais, si possible sous 72 heures.",
    ),
)


def _tokens(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


def _bucket(token: str) -> int:
    return int(hashlib.sha256(token.encode("utf-8")).hexdigest()[:7], 16)


class FakeEmbedder:
    embedding_id = "fake-000000"
    dense_size = DIM

    def __init__(self) -> None:
        self.documents_embedded = 0

    def _embed(self, text: str) -> Embedded:
        counts = Counter(_bucket(t) for t in _tokens(text))
        dense = [0.0] * DIM
        for bucket, count in counts.items():
            dense[bucket % DIM] += count
        norm = math.sqrt(sum(v * v for v in dense)) or 1.0
        indices = tuple(sorted(counts))
        sparse = SparseVector(indices, tuple(float(counts[i]) for i in indices))
        return Embedded(tuple(v / norm for v in dense), sparse)

    def embed_documents(self, texts: Sequence[str]) -> list[Embedded]:
        self.documents_embedded += len(texts)
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> Embedded:
        return self._embed(text)


def write_mini_corpus(directory: Path) -> Path:
    write_chunks(directory / "DORA.jsonl", [c for c in MINI_CORPUS if c.regulation == "DORA"])
    write_chunks(directory / "RGPD.jsonl", [c for c in MINI_CORPUS if c.regulation == "RGPD"])
    return directory


def local_settings(tmp_path: Path, **overrides: object) -> Settings:
    """Settings for an on-disk Qdrant folder and a mini corpus, both under tmp_path."""
    values: dict[str, object] = {
        "qdrant_path": str(tmp_path / "qdrant"),
        "corpus_dir": write_mini_corpus(tmp_path / "corpus"),
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)  # type: ignore[arg-type]


def indexed_settings(tmp_path: Path, **overrides: object) -> Settings:
    """local_settings, with the mini corpus already indexed by the fake embedder."""
    settings = local_settings(tmp_path, **overrides)
    client = open_client(settings)
    try:
        build_index(client, read_corpus_dir(settings.corpus_dir), FakeEmbedder(), prefix="vigie")
    finally:
        client.close()
    return settings
