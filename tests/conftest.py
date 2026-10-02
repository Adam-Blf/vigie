from pathlib import Path

import pytest

from vigie.config import Settings

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def excerpt() -> bytes:
    return (FIXTURES / "corpus_excerpt.xhtml").read_bytes()


@pytest.fixture
def corpus_settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        corpus_dir=tmp_path / "corpus",
        corpus_cache_dir=tmp_path / "cache",
        corpus_lock_path=tmp_path / "corpus.lock",
    )
