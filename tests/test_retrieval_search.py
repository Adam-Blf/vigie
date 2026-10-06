import pytest
from qdrant_client import QdrantClient
from tests.retrieval_fixtures import MINI_CORPUS, FakeEmbedder

from vigie.rag.pipeline import Retriever
from vigie.retrieval.index import build_index
from vigie.retrieval.search import CollectionMissingError, QdrantRetriever


@pytest.fixture
def retriever() -> QdrantRetriever:
    client = QdrantClient(location=":memory:")
    embedder = FakeEmbedder()
    name = build_index(client, MINI_CORPUS, embedder, prefix="vigie").collection
    return QdrantRetriever(client, name, embedder, prefetch_limit=20)


def test_article_28_dora_comes_first(retriever: QdrantRetriever) -> None:
    passages = retriever.search("article 28 DORA", top_k=3)
    assert passages[0].label == "[DORA art. 28 §1]"
    # RGPD article 28 shares "article 28" but not the regulation, so it ranks below.
    assert [p.article_id for p in passages].index("RGPD:28") > 0


def test_passages_carry_the_chunk_fields_and_a_fused_score(retriever: QdrantRetriever) -> None:
    top = retriever.search("notification violation de données 72 heures", top_k=5)[0]
    source = MINI_CORPUS[4]
    assert (top.regulation, top.article, top.paragraph) == ("RGPD", "33", None)
    assert (top.title, top.text, top.url, top.eid) == (
        source.title,
        source.text,
        source.url,
        source.eid,
    )
    # First in both the dense and the BM25 list: 1/2 + 1/2 with Qdrant's RRF constant.
    assert top.score == pytest.approx(1.0)


def test_scores_are_sorted_and_top_k_is_respected(retriever: QdrantRetriever) -> None:
    passages = retriever.search("entité financière prestataire", top_k=4)
    assert len(passages) == 4
    assert [p.score for p in passages] == sorted((p.score for p in passages), reverse=True)


def test_regulation_filter_keeps_only_that_text(retriever: QdrantRetriever) -> None:
    passages = retriever.search("article 28 DORA", top_k=5, regulations=["rgpd"])
    assert {p.regulation for p in passages} == {"RGPD"}
    assert len(passages) == 2


def test_empty_filter_means_every_text(retriever: QdrantRetriever) -> None:
    assert len(retriever.search("article", top_k=5, regulations=[])) == 5


def test_fits_the_pipeline_protocol(retriever: QdrantRetriever) -> None:
    as_protocol: Retriever = retriever
    assert as_protocol.search("article 28 DORA", 1)[0].article_id == "DORA:28"
    assert retriever.collection.startswith("vigie_fake-000000_")


def test_missing_collection_is_reported_with_the_fix() -> None:
    with pytest.raises(CollectionMissingError, match="run vigie-index"):
        QdrantRetriever(
            QdrantClient(location=":memory:"), "vigie_x_y", FakeEmbedder(), prefetch_limit=5
        )
