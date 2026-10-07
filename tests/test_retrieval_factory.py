from pathlib import Path

import pytest
from tests.retrieval_fixtures import FakeEmbedder, indexed_settings, local_settings

from vigie.config import Settings
from vigie.rag.static_retriever import StaticRetriever
from vigie.retrieval import client as client_module
from vigie.retrieval import factory
from vigie.retrieval.client import QdrantNotConfiguredError, open_client
from vigie.retrieval.factory import RetrieverConfigError, open_retriever, resolve_collection
from vigie.retrieval.search import QdrantRetriever

PASSAGES = Path(__file__).parent / "fixtures" / "dora_art28_passages.json"


def test_settings_default_to_qdrant_with_french_bm25() -> None:
    settings = Settings(_env_file=None)
    assert settings.retriever == "qdrant"
    assert settings.sparse_language == "french"
    assert settings.collection_prefix == "vigie"
    assert settings.qdrant_collection is None
    assert settings.retrieval_prefetch_limit == 20
    assert settings.retrieval_rrf_k == 60


def test_client_prefers_the_server_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # A real remote client asks the server for its version on creation; the recorder keeps
    # the unit test off the network.
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(client_module, "QdrantClient", lambda **kwargs: calls.append(kwargs))
    settings = Settings(
        _env_file=None,
        qdrant_url="http://127.0.0.1:6733",
        qdrant_api_key="k",
        qdrant_path=str(tmp_path),
    )
    open_client(settings)
    assert calls == [{"url": "http://127.0.0.1:6733", "api_key": "k"}]


def test_client_memory_and_folder_modes(tmp_path: Path) -> None:
    for path in (":memory:", str(tmp_path / "q")):
        client = open_client(Settings(_env_file=None, qdrant_path=path))
        assert client.get_collections().collections == []
        client.close()
    assert (tmp_path / "q").is_dir()


def test_client_without_any_location_says_what_to_set() -> None:
    with pytest.raises(QdrantNotConfiguredError, match="VIGIE_QDRANT_URL"):
        open_client(Settings(_env_file=None))


def test_passages_argument_forces_the_static_retriever(tmp_path: Path) -> None:
    with open_retriever(local_settings(tmp_path), passages=PASSAGES) as retriever:
        assert isinstance(retriever, StaticRetriever)


def test_static_retriever_from_settings(tmp_path: Path) -> None:
    settings = local_settings(tmp_path, retriever="static", static_passages_path=PASSAGES)
    with open_retriever(settings) as retriever:
        assert retriever.search("ignored", 1)[0].label == "[DORA art. 28 §1]"


def test_static_retriever_without_a_file_is_a_config_error(tmp_path: Path) -> None:
    settings = local_settings(tmp_path, retriever="static")
    with (
        pytest.raises(RetrieverConfigError, match="VIGIE_STATIC_PASSAGES_PATH"),
        open_retriever(settings),
    ):
        pass


def test_qdrant_retriever_on_the_derived_collection(tmp_path: Path) -> None:
    settings = indexed_settings(tmp_path)
    with open_retriever(settings, embedder=FakeEmbedder()) as retriever:
        assert isinstance(retriever, QdrantRetriever)
        assert retriever.search("article 28 DORA", 1)[0].article_id == "DORA:28"
    # Closed on exit: the local folder can be opened again by someone else.
    open_client(settings).close()


def test_default_embedder_comes_from_the_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = indexed_settings(tmp_path)
    seen: list[Settings] = []

    def fake_from_settings(given: Settings) -> FakeEmbedder:
        seen.append(given)
        return FakeEmbedder()

    monkeypatch.setattr(factory.FastEmbedEmbedder, "from_settings", fake_from_settings)
    with open_retriever(settings) as retriever:
        assert isinstance(retriever, QdrantRetriever)
    assert seen == [settings]


def test_pinned_collection_wins_without_reading_the_corpus(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, qdrant_collection="vigie_pinned", corpus_dir=tmp_path)
    assert resolve_collection(settings, FakeEmbedder()) == "vigie_pinned"


def test_no_corpus_and_no_pin_is_a_config_error(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, corpus_dir=tmp_path / "empty")
    with pytest.raises(RetrieverConfigError, match="VIGIE_QDRANT_COLLECTION"):
        resolve_collection(settings, FakeEmbedder())


@pytest.mark.parametrize(("rrf_k", "top_score"), [(60, 2 / 60), (0, 1.0)])
def test_rrf_constant_comes_from_the_settings(tmp_path: Path, rrf_k: int, top_score: float) -> None:
    # First in both lists: 2/k with a constant, 1/2 + 1/2 with the plain FusionQuery.
    # Equal weights, so the score shows the constant alone.
    settings = indexed_settings(tmp_path, retrieval_rrf_k=rrf_k, retrieval_dense_weight=1.0)
    with open_retriever(settings, embedder=FakeEmbedder()) as retriever:
        top = retriever.search("notification violation de données 72 heures", 1)[0]
    assert top.article_id == "RGPD:33"
    assert top.score == pytest.approx(top_score)


def test_a_rerank_model_in_the_settings_builds_the_reranker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    built: list[tuple[str, Path | None]] = []

    class Recorder:
        def __init__(self, model: str, cache_dir: Path | None = None) -> None:
            built.append((model, cache_dir))
            self.model = model

        def scores(self, query: str, documents: list[str]) -> list[float]:
            return [0.0] * len(documents)

    monkeypatch.setattr(factory, "FastEmbedReranker", Recorder)
    settings = indexed_settings(tmp_path, rerank_model="jina", rerank_depth=7)
    with open_retriever(settings, embedder=FakeEmbedder()) as retriever:
        assert isinstance(retriever, QdrantRetriever)
        assert retriever.search("article 28 DORA", 2)[0].score == 0.5
    assert built == [("jina", None)]
    # Without the setting no reranker is built at all.
    with open_retriever(indexed_settings(tmp_path / "b"), embedder=FakeEmbedder()):
        pass
    assert len(built) == 1
