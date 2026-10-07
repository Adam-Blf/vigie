from collections.abc import Iterable, Sequence
from pathlib import Path

import pytest
from tests.rag_fixtures import passage

from vigie.retrieval.rerank import FastEmbedReranker, passage_text, rerank, sigmoid


class LengthReranker:
    """Scores a document by its length, which makes the expected order obvious."""

    model = "length"

    def __init__(self) -> None:
        self.calls: list[tuple[str, list[str]]] = []

    def scores(self, query: str, documents: Sequence[str]) -> list[float]:
        self.calls.append((query, list(documents)))
        return [float(len(d)) - 60.0 for d in documents]


class StubEncoder:
    def __init__(self, model: str, cache_dir: str | None) -> None:
        self.model = model
        self.cache_dir = cache_dir

    def rerank(self, query: str, documents: Iterable[str]) -> Iterable[float]:
        return (float(len(d)) for d in documents)


def test_sigmoid_is_bounded_and_stable() -> None:
    assert sigmoid(0.0) == 0.5
    assert 0.0 < sigmoid(-1000.0) < 1e-300 or sigmoid(-1000.0) == 0.0
    assert sigmoid(1000.0) == 1.0
    assert sigmoid(-2.0) == pytest.approx(1 - sigmoid(2.0))


def test_rerank_reorders_keeps_top_k_and_maps_scores_into_0_1() -> None:
    short = passage("5", text="court")
    long = passage("28", text="un texte nettement plus long que les autres passages")
    middle = passage("30", text="un texte moyen")
    reranker = LengthReranker()

    ranked = rerank(reranker, "question", [short, middle, long], top_k=2)

    assert [p.article for p in ranked] == ["28", "30"]
    assert all(0.0 < p.score < 1.0 for p in ranked)
    assert ranked[0].score > ranked[1].score
    # The reranker reads the same header as the index, so "DORA article 28" is visible.
    assert reranker.calls[0][1][2] == passage_text(long)
    assert passage_text(long).startswith("DORA article 28 ")


def test_nothing_to_rerank_costs_no_model_call() -> None:
    reranker = LengthReranker()
    assert rerank(reranker, "question", [], top_k=3) == []
    assert reranker.calls == []


def test_fastembed_reranker_wraps_the_cross_encoder(tmp_path: Path) -> None:
    reranker = FastEmbedReranker("jina", tmp_path, factory=StubEncoder)
    assert reranker.model == "jina"
    assert reranker.scores("q", ["ab", "abcd"]) == [2.0, 4.0]
    assert isinstance(reranker._encoder, StubEncoder)
    assert reranker._encoder.cache_dir == str(tmp_path)
    assert FastEmbedReranker("jina", factory=StubEncoder)._encoder.cache_dir is None  # type: ignore[attr-defined]


def test_the_default_factory_opens_fastembed_s_cross_encoder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fastembed.rerank import cross_encoder

    monkeypatch.setattr(
        cross_encoder,
        "TextCrossEncoder",
        lambda model_name, cache_dir: StubEncoder(model_name, cache_dir),
    )
    reranker = FastEmbedReranker("jinaai/jina-reranker-v2-base-multilingual", tmp_path)
    assert isinstance(reranker._encoder, StubEncoder)
    assert reranker._encoder.model == "jinaai/jina-reranker-v2-base-multilingual"
