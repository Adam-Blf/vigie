import io
import json
from pathlib import Path

import pytest
from tests.retrieval_fixtures import FakeEmbedder, indexed_settings

from vigie.config import get_settings
from vigie.rag.cli import main
from vigie.rag.static_retriever import StaticRetriever
from vigie.retrieval import factory

FIXTURE = Path(__file__).parent / "fixtures" / "dora_art28_passages.json"


def test_fixture_holds_three_paragraphs_of_dora_article_28() -> None:
    passages = StaticRetriever.from_json(FIXTURE).search("ignored", top_k=6)
    assert [p.label for p in passages] == [
        "[DORA art. 28 §1]",
        "[DORA art. 28 §3]",
        "[DORA art. 28 §4]",
    ]
    assert StaticRetriever.from_json(FIXTURE).search("ignored", top_k=1)[0].score == 0.92


def test_cli_streams_then_prints_the_validated_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIGIE_LLM_PROVIDER", "fake")
    monkeypatch.setenv("FAKE_LLM_HALLUCINATE", "1")
    get_settings.cache_clear()
    out, live = io.StringIO(), io.StringIO()
    try:
        code = main(["Que doit faire une banque ?", "--passages", str(FIXTURE)], out, live)
    finally:
        get_settings.cache_clear()

    assert code == 0
    assert "[DORA art. 999 §9]" in live.getvalue()
    report = json.loads(out.getvalue())
    assert report["prompt_version"] == "v2"
    assert report["refused"] is False
    assert report["removed_citations"] == ["[DORA art. 999 §9]"]
    assert "[DORA art. 999 §9]" not in report["text"]
    assert {c["label"] for c in report["citations"]} == {
        "[DORA art. 28 §1]",
        "[DORA art. 28 §3]",
        "[DORA art. 28 §4]",
    }


def test_cli_without_passages_retrieves_from_qdrant(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = indexed_settings(tmp_path)
    monkeypatch.setenv("VIGIE_LLM_PROVIDER", "fake")
    # A .env written by `tasks.py up` sets VIGIE_QDRANT_URL, and a server URL wins over the
    # local path: blank it so this test never depends on whether the stack was started.
    monkeypatch.setenv("VIGIE_QDRANT_URL", "")
    monkeypatch.setenv("VIGIE_QDRANT_PATH", str(settings.qdrant_path))
    monkeypatch.setenv("VIGIE_CORPUS_DIR", str(settings.corpus_dir))
    monkeypatch.setattr(factory.FastEmbedEmbedder, "from_settings", lambda s: FakeEmbedder())
    get_settings.cache_clear()
    out, live = io.StringIO(), io.StringIO()
    try:
        code = main(["Que dit l'article 28 de DORA ?"], out, live)
    finally:
        get_settings.cache_clear()

    assert code == 0
    report = json.loads(out.getvalue())
    assert report["refused"] is False
    assert report["sources"][0]["eid"] == "art_28.par_1"
    assert "[DORA art. 28 §1]" in {c["label"] for c in report["citations"]}


def test_usage_names_the_module_command(capsys: pytest.CaptureFixture[str]) -> None:
    # No console script is installed, so the usage line must show the command that works.
    with pytest.raises(SystemExit):
        main(["--help"])
    assert capsys.readouterr().out.startswith("usage: python -m vigie.rag.cli")
