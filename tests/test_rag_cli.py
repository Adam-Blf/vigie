import io
import json
from pathlib import Path

import pytest

from vigie.config import get_settings
from vigie.rag.cli import main
from vigie.rag.static_retriever import StaticRetriever

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


def test_usage_names_the_module_command(capsys: pytest.CaptureFixture[str]) -> None:
    # No console script is installed, so the usage line must show the command that works.
    with pytest.raises(SystemExit):
        main(["--help"])
    assert capsys.readouterr().out.startswith("usage: python -m vigie.rag.cli")
