from pathlib import Path

import pytest
from tests.retrieval_fixtures import FakeEmbedder, local_settings

from vigie.retrieval import cli
from vigie.retrieval.cli import EXIT_FAILED, EXIT_OK, main


def test_index_then_reindex_is_a_no_op(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    settings = local_settings(tmp_path)

    assert main([], settings, FakeEmbedder()) == EXIT_OK
    first = capsys.readouterr().out
    assert "chunks read  5" in first
    assert "embedded     5" in first
    assert "points       5" in first
    assert "collection   vigie_fake-000000_" in first

    assert main([], settings, FakeEmbedder()) == EXIT_OK
    second = capsys.readouterr().out
    assert "complete already, nothing embedded" in second
    assert "points       5" in second

    assert main(["--force"], settings, FakeEmbedder()) == EXIT_OK
    assert "embedded     5" in capsys.readouterr().out


def test_corpus_argument_overrides_the_setting(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    settings = local_settings(tmp_path, corpus_dir=tmp_path / "nowhere")
    assert main(["--corpus", str(tmp_path / "corpus")], settings, FakeEmbedder()) == EXIT_OK
    assert "chunks read  5" in capsys.readouterr().out


def test_empty_corpus_fails_before_touching_qdrant(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    settings = local_settings(tmp_path, corpus_dir=tmp_path / "empty")
    assert main([], settings, FakeEmbedder()) == EXIT_FAILED
    assert "run vigie-ingest first" in capsys.readouterr().err
    assert not (tmp_path / "qdrant").exists()


def test_missing_qdrant_location_fails_clearly(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    settings = local_settings(tmp_path, qdrant_path=None)
    assert main([], settings, FakeEmbedder()) == EXIT_FAILED
    assert "VIGIE_QDRANT_PATH" in capsys.readouterr().err


def test_defaults_come_from_the_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    local = local_settings(tmp_path)
    monkeypatch.setattr(cli, "get_settings", lambda: local)
    monkeypatch.setattr(cli.FastEmbedEmbedder, "from_settings", lambda s: FakeEmbedder())
    assert main([]) == EXIT_OK
    assert "points       5" in capsys.readouterr().out
