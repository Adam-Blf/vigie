from pathlib import Path

import pytest

from vigie.config import Settings, get_settings
from vigie.evaluation.cli import build_parser


def test_golden_paths_default_to_the_versioned_files() -> None:
    settings = Settings(_env_file=None)
    assert settings.golden_path == Path("data/golden/questions.jsonl")
    assert settings.golden_seal_path == Path("data/golden/test.sha256")


def test_cli_defaults_follow_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIGIE_GOLDEN_PATH", "elsewhere/q.jsonl")
    monkeypatch.setenv("VIGIE_CORPUS_DIR", "elsewhere/corpus")
    get_settings.cache_clear()
    try:
        args = build_parser().parse_args(["validate-golden"])
    finally:
        get_settings.cache_clear()
    assert args.golden == Path("elsewhere/q.jsonl")
    assert args.corpus == Path("elsewhere/corpus")
