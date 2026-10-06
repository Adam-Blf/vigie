import pytest
from qdrant_client import QdrantClient
from tests.retrieval_fixtures import MINI_CORPUS, FakeEmbedder

from vigie.retrieval.index import build_index
from vigie.retrieval.language import is_english
from vigie.retrieval.search import QdrantRetriever


@pytest.mark.parametrize(
    ("question", "english"),
    [
        ("What is the highest GDPR fine a company can face?", True),
        ("Does the AI Act require human oversight?", True),
        ("Quel registre une banque doit-elle tenir sur ses prestataires ?", False),
        ("Que prévoit l'article 28 DORA ?", False),
        ("DORA article 28", False),
        ("", False),
    ],
)
def test_function_words_decide_and_ties_stay_french(question: str, english: bool) -> None:
    assert is_english(question) is english


class CountingClient:
    """Wraps the in-memory client to count the branches of each query."""

    def __init__(self, inner: QdrantClient) -> None:
        self.inner = inner
        self.branches: list[int] = []

    def collection_exists(self, name: str) -> bool:
        return self.inner.collection_exists(name)

    def query_points(self, *args: object, **kwargs: object) -> object:
        self.branches.append(len(kwargs["prefetch"]))  # type: ignore[arg-type]
        return self.inner.query_points(*args, **kwargs)  # type: ignore[arg-type]


def retriever(**options: object) -> tuple[QdrantRetriever, CountingClient]:
    inner = QdrantClient(location=":memory:")
    embedder = FakeEmbedder()
    name = build_index(inner, MINI_CORPUS, embedder, prefix="vigie").collection
    client = CountingClient(inner)
    found = QdrantRetriever(client, name, embedder, prefetch_limit=20, rrf_k=60, **options)  # type: ignore[arg-type]
    return found, client


def test_english_questions_skip_bm25_only_when_asked() -> None:
    gated, client = retriever(sparse_on_english=False)
    gated.search("What does the regulation say about the 72 hours notification?", 3)
    gated.search("Que dit le texte sur la notification sous 72 heures ?", 3)
    assert client.branches == [1, 2]

    plain, client = retriever()
    plain.search("What does the regulation say about the 72 hours notification?", 3)
    assert client.branches == [2]


def test_a_dense_weight_keeps_rrf_scores_and_order_sorted() -> None:
    weighted, _ = retriever(dense_weight=2.0)
    found = weighted.search("notification violation de données 72 heures", 3)
    assert found[0].article_id == "RGPD:33"
    assert [p.score for p in found] == sorted((p.score for p in found), reverse=True)
    # Still a rank score of the RRF family, far below a cosine: the pipeline's floor of 0
    # keeps every passage, as it does without weights.
    assert 0.0 < found[-1].score <= found[0].score < 0.1
