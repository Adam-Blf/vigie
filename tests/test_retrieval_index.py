import re

import pytest
from qdrant_client import QdrantClient
from tests.retrieval_fixtures import DIM, MINI_CORPUS, FakeEmbedder

from vigie.corpus.models import Chunk
from vigie.retrieval.index import (
    DENSE,
    SPARSE,
    build_index,
    collection_name,
    corpus_sha256,
    document_text,
    point_id,
)


@pytest.fixture
def client() -> QdrantClient:
    return QdrantClient(location=":memory:")


def test_point_id_is_stable_and_unique() -> None:
    ids = [point_id(c) for c in MINI_CORPUS]
    assert len(set(ids)) == len(ids)
    assert ids == [point_id(c) for c in MINI_CORPUS]
    # Pinned value: if this moves, every deployed index silently gets new ids.
    assert point_id(MINI_CORPUS[0]) == "51b347a6-c51e-5e18-9334-b4c1aa5ca332"


def test_point_id_ignores_the_text_but_not_the_reference() -> None:
    first = MINI_CORPUS[0]
    assert point_id(first.model_copy(update={"text": "autre"})) == point_id(first)
    assert point_id(first.model_copy(update={"paragraph": "2"})) != point_id(first)


def test_collection_name_follows_the_bundle_convention() -> None:
    name = collection_name("vigie", "fake-000000", MINI_CORPUS)
    assert re.fullmatch(r"vigie_fake-000000_[0-9a-f]{8}", name)
    assert name.endswith(corpus_sha256(MINI_CORPUS)[:8])


def test_corpus_fingerprint_ignores_order_but_not_content() -> None:
    reordered = tuple(reversed(MINI_CORPUS))
    assert corpus_sha256(reordered) == corpus_sha256(MINI_CORPUS)
    edited = (MINI_CORPUS[0].model_copy(update={"text": "modifié"}), *MINI_CORPUS[1:])
    assert corpus_sha256(edited) != corpus_sha256(MINI_CORPUS)


def test_document_text_puts_the_reference_first() -> None:
    assert document_text(MINI_CORPUS[0]).startswith("DORA article 28 Principes généraux\n")


def test_build_creates_named_vectors_and_full_payload(client: QdrantClient) -> None:
    report = build_index(client, MINI_CORPUS, FakeEmbedder(), prefix="vigie")

    assert (report.chunks, report.indexed, report.skipped) == (5, 5, False)
    info = client.get_collection(report.collection)
    vectors = info.config.params.vectors
    assert isinstance(vectors, dict) and vectors[DENSE].size == DIM
    assert info.config.params.sparse_vectors is not None
    assert SPARSE in info.config.params.sparse_vectors
    record = client.retrieve(report.collection, [point_id(MINI_CORPUS[3])])[0]
    assert Chunk.model_validate(record.payload) == MINI_CORPUS[3]


def test_second_build_skips_and_force_rewrites_the_same_points(client: QdrantClient) -> None:
    embedder = FakeEmbedder()
    first = build_index(client, MINI_CORPUS, embedder, prefix="vigie")
    again = build_index(client, MINI_CORPUS, embedder, prefix="vigie")
    assert again.skipped and again.indexed == 0
    assert embedder.documents_embedded == 5

    forced = build_index(client, MINI_CORPUS, embedder, prefix="vigie", force=True)
    assert not forced.skipped and embedder.documents_embedded == 10
    assert forced.collection == first.collection
    assert client.count(first.collection, exact=True).count == 5


def test_an_incomplete_collection_is_completed(client: QdrantClient) -> None:
    embedder = FakeEmbedder()
    name = build_index(client, MINI_CORPUS, embedder, prefix="vigie").collection
    client.delete(name, points_selector=[point_id(MINI_CORPUS[0])])
    report = build_index(client, MINI_CORPUS, embedder, prefix="vigie")
    assert not report.skipped
    assert client.count(name, exact=True).count == 5


def test_screen_quarantines_flagged_chunks(client: QdrantClient) -> None:
    flagged = MINI_CORPUS[2]
    name = build_index(client, MINI_CORPUS, FakeEmbedder(), prefix="vigie").collection

    def screen(chunk: Chunk) -> str | None:
        return "injection" if chunk is flagged else None

    report = build_index(client, MINI_CORPUS, FakeEmbedder(), prefix="vigie", screen=screen)

    assert [(q.chunk, q.reason) for q in report.quarantined] == [(flagged, "injection")]
    # Indexed by the first, unscreened run, the flagged chunk is removed by the second.
    assert client.retrieve(name, [point_id(flagged)]) == []
    assert client.count(name, exact=True).count == 4
    assert report.skipped


def test_screen_on_a_new_collection_never_indexes_the_chunk(client: QdrantClient) -> None:
    report = build_index(
        client, MINI_CORPUS, FakeEmbedder(), prefix="vigie", screen=lambda c: "pii"
    )
    assert report.indexed == 0 and len(report.quarantined) == 5
    assert client.count(report.collection, exact=True).count == 0
