"""Build the Qdrant collection from the corpus chunks, safely re-runnable.

Every chunk gets a point id derived from what it is (regulation, article, paragraph,
ELI anchor), never from the order it was read in. Running the build twice therefore
rewrites the same points instead of piling up duplicates, and a chunk keeps its id
across machines, which keeps traces and evaluation runs comparable.
"""

from __future__ import annotations

import hashlib
import uuid
import warnings
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from qdrant_client import QdrantClient, models

from vigie.corpus.models import Chunk
from vigie.retrieval.embeddings import Embedded, Embedder

DENSE = "dense"
SPARSE = "bm25"
# Fixed namespace so ids are the same on every machine; changing it re-keys the index.
POINT_NAMESPACE = uuid.UUID("6f1f0c8e-4a52-5d4b-9e2a-56a1e0a2d7c1")
UPSERT_BATCH = 64

# Returns why a chunk must stay out of the index, or None when it is fine. The input guard
# chain (J4) plugs in here: a passage carrying an injection would otherwise reach the
# prompt through retrieval, which is the indirect injection path of the risk map.
ChunkScreen = Callable[[Chunk], "str | None"]


@dataclass(frozen=True)
class Quarantined:
    chunk: Chunk
    reason: str


@dataclass(frozen=True)
class IndexReport:
    collection: str
    chunks: int
    indexed: int
    skipped: bool
    quarantined: list[Quarantined] = field(default_factory=list)


def point_id(chunk: Chunk) -> str:
    key = f"{chunk.regulation}/{chunk.article}/{chunk.paragraph or ''}/{chunk.eid}"
    return str(uuid.uuid5(POINT_NAMESPACE, key))


def corpus_sha256(chunks: Sequence[Chunk]) -> str:
    """Fingerprint of the chunks themselves, so a parser change moves it as well as a text.

    Sorted by point id first: the fingerprint must not depend on the order files were read.
    """
    lines = sorted((point_id(c), c.model_dump_json()) for c in chunks)
    digest = hashlib.sha256()
    for _, line in lines:
        digest.update(line.encode("utf-8") + b"\n")
    return digest.hexdigest()


def collection_name(prefix: str, embedding_id: str, chunks: Sequence[Chunk]) -> str:
    return f"{prefix}_{embedding_id}_{corpus_sha256(chunks)[:8]}"


def document_text(chunk: Chunk) -> str:
    """What gets embedded: the reference and the heading, then the body.

    The body alone rarely says "article 28" or "DORA", yet that is how people ask; putting
    the reference in front gives BM25 something to match on such questions.
    """
    return f"{chunk.regulation} article {chunk.article} {chunk.title}\n{chunk.text}"


def ensure_collection(client: QdrantClient, name: str, dense_size: int) -> bool:
    """Create the collection if needed; True when it was created by this call."""
    if client.collection_exists(name):
        return False
    client.create_collection(
        name,
        vectors_config={
            DENSE: models.VectorParams(size=dense_size, distance=models.Distance.COSINE)
        },
        # BM25 only works with the IDF part computed by Qdrant across the whole collection.
        sparse_vectors_config={SPARSE: models.SparseVectorParams(modifier=models.Modifier.IDF)},
    )
    # The regulation filter is the common one. Local mode ignores payload indexes and warns
    # about it on every build; the index matters on the server only.
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Payload indexes have no effect")
        client.create_payload_index(name, "regulation", models.PayloadSchemaType.KEYWORD)
    return True


def _point(chunk: Chunk, vectors: Embedded) -> models.PointStruct:
    sparse = models.SparseVector(
        indices=list(vectors.sparse.indices), values=list(vectors.sparse.values)
    )
    return models.PointStruct(
        id=point_id(chunk),
        vector={DENSE: list(vectors.dense), SPARSE: sparse},
        payload=chunk.model_dump(mode="json"),
    )


def build_index(
    client: QdrantClient,
    chunks: Sequence[Chunk],
    embedder: Embedder,
    *,
    prefix: str,
    screen: ChunkScreen | None = None,
    force: bool = False,
) -> IndexReport:
    """Index the accepted chunks; skip the embedding work when the collection is complete.

    The name already encodes the model and the corpus, so a collection holding exactly the
    expected number of points is the one this call would build. `force` re-embeds anyway.
    """
    name = collection_name(prefix, embedder.embedding_id, chunks)
    quarantined: list[Quarantined] = []
    accepted: list[Chunk] = []
    for chunk in chunks:
        reason = screen(chunk) if screen else None
        if reason is None:
            accepted.append(chunk)
        else:
            quarantined.append(Quarantined(chunk, reason))

    created = ensure_collection(client, name, embedder.dense_size)
    if quarantined and not created:
        # A chunk indexed by an earlier run with a laxer screen must not stay searchable.
        ids: list[models.ExtendedPointId] = [point_id(q.chunk) for q in quarantined]
        client.delete(name, points_selector=models.PointIdsList(points=ids), wait=True)
    if not created and not force and client.count(name, exact=True).count == len(accepted):
        return IndexReport(name, len(chunks), 0, True, quarantined)

    for start in range(0, len(accepted), UPSERT_BATCH):
        batch = accepted[start : start + UPSERT_BATCH]
        vectors = embedder.embed_documents([document_text(c) for c in batch])
        points = [_point(c, v) for c, v in zip(batch, vectors, strict=True)]
        client.upsert(name, points=points, wait=True)
    return IndexReport(name, len(chunks), len(accepted), False, quarantined)
