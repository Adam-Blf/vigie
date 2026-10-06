from collections.abc import Sequence
from dataclasses import replace

from qdrant_client import QdrantClient
from tests.rag_fixtures import passage
from tests.retrieval_fixtures import MINI_CORPUS, FakeEmbedder

from vigie.retrieval.index import build_index
from vigie.retrieval.search import PINNED_PER_REFERENCE, QdrantRetriever, pin_references

# The words of DORA article 5, with article 30 named: the models prefer article 5, the
# reference must win.
QUESTION = "organe de direction responsabilité ultime gestion du risque TIC, article 30 DORA"


def retriever(**options: object) -> QdrantRetriever:
    client = QdrantClient(location=":memory:")
    embedder = FakeEmbedder()
    name = build_index(client, MINI_CORPUS, embedder, prefix="vigie").collection
    return QdrantRetriever(client, name, embedder, prefetch_limit=20, **options)  # type: ignore[arg-type]


class ReverseReranker:
    """Prefers whatever the fusion liked least, so its effect cannot be mistaken."""

    model = "reverse"

    def scores(self, query: str, documents: Sequence[str]) -> list[float]:
        return [float(i) for i in range(len(documents))]


def test_without_pinning_the_models_put_article_5_first() -> None:
    assert retriever().search(QUESTION, top_k=3)[0].article_id == "DORA:5"


def test_a_named_article_comes_first_with_the_best_score() -> None:
    found = retriever(pin_references=True).search(QUESTION, top_k=3)
    assert found[0].article_id == "DORA:30"
    assert found[0].score == max(p.score for p in found)
    assert len(found) == 3
    assert len({(p.regulation, p.eid) for p in found}) == 3


def test_a_regulation_filter_drops_references_to_other_texts() -> None:
    found = retriever(pin_references=True).search(QUESTION, top_k=3, regulations=["RGPD"])
    assert {p.regulation for p in found} == {"RGPD"}


def test_an_article_absent_from_the_index_changes_nothing() -> None:
    plain = retriever().search("article 77 DORA organe de direction", top_k=3)
    pinned = retriever(pin_references=True).search("article 77 DORA organe de direction", top_k=3)
    assert [p.eid for p in pinned] == [p.eid for p in plain]


def test_the_reranker_reorders_a_wider_pool_then_the_cut_applies() -> None:
    plain = retriever().search("gestion du risque", top_k=5)
    reranked = retriever(reranker=ReverseReranker(), rerank_depth=5).search(
        "gestion du risque", top_k=2
    )
    assert [p.eid for p in reranked] == [p.eid for p in reversed(plain)][:2]
    assert all(0.0 < p.score < 1.0 for p in reranked)


def test_pinning_keeps_found_chunks_in_order_then_paragraph_order_and_caps_them() -> None:
    ranked = [passage("5", "1", score=0.5), passage("28", "4", score=0.4)]
    named = [[passage("28", str(n), score=0.0) for n in (9, 2, 4, 1, 3)]]

    result = pin_references(ranked, named, top_k=10)

    pinned = result[:PINNED_PER_REFERENCE]
    assert [p.paragraph for p in pinned] == ["4", "1", "2"]
    assert all(p.score == 0.5 for p in pinned)
    assert [p.article_id for p in result[PINNED_PER_REFERENCE:]] == ["DORA:5"]


def test_pinning_an_empty_ranking_scores_one_and_sorts_odd_paragraphs_last() -> None:
    odd = replace(passage("28", None, score=0.0), paragraph="a")
    named = [[odd, passage("28", "2", score=0.0)]]
    result = pin_references([], named, top_k=5)
    assert [p.paragraph for p in result] == ["2", "a"]
    assert {p.score for p in result} == {1.0}
