from pathlib import Path

import pytest

from vigie.config import Settings
from vigie.corpus import cli
from vigie.corpus.fetch import FetchError
from vigie.corpus.jsonl import read_chunks
from vigie.corpus.lock import read_lock, write_lock
from vigie.corpus.models import Chunk
from vigie.corpus.remote import RemoteCorpusError
from vigie.corpus.sources import Regulation


class FakeCellar:
    """Serves the committed excerpt for every regulation and writes it like the real cache."""

    payload: bytes = b""
    fail = False
    closed = 0

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def cache_path(self, regulation: Regulation) -> Path:
        return self._settings.corpus_cache_dir / f"{regulation.celex}.xhtml"

    def fetch(self, regulation: Regulation) -> bytes:
        if FakeCellar.fail:
            raise FetchError("gave up on cellar after 5 attempts (HTTP 503)")
        path = self.cache_path(regulation)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(FakeCellar.payload)
        return FakeCellar.payload

    def close(self) -> None:
        FakeCellar.closed += 1


@pytest.fixture(autouse=True)
def fake_cellar(monkeypatch: pytest.MonkeyPatch, excerpt: bytes) -> None:
    FakeCellar.payload = excerpt
    FakeCellar.fail = False
    FakeCellar.closed = 0
    monkeypatch.setattr(cli, "CellarClient", FakeCellar)


def run(settings: Settings, *args: str) -> int:
    return cli.main(list(args), settings)


def test_missing_lock_asks_for_an_explicit_first_run(
    corpus_settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run(corpus_settings) == cli.EXIT_USAGE
    assert "--update-lock" in capsys.readouterr().err


def test_first_run_writes_the_lock_and_one_jsonl_per_text(
    corpus_settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run(corpus_settings, "--update-lock") == cli.EXIT_OK
    lock = read_lock(corpus_settings.corpus_lock_path)
    assert sorted(lock.texts) == ["AIACT", "AMLR", "DORA", "RGPD"]
    assert lock.texts["DORA"].articles == 4
    assert len(lock.texts["DORA"].sha256) == 64
    chunks = read_chunks(corpus_settings.corpus_dir / "DORA.jsonl")
    assert {c.retrieved_on for c in chunks} == {lock.texts["DORA"].downloaded_at}
    out = capsys.readouterr().out
    assert "DORA   32022R2554  articles=4    annexes=1" in out
    assert FakeCellar.closed == 1


def test_second_run_checks_against_the_lock(corpus_settings: Settings) -> None:
    run(corpus_settings, "--update-lock")
    assert run(corpus_settings, "--only", "dora", "--recitals") == cli.EXIT_OK
    chunks = read_chunks(corpus_settings.corpus_dir / "DORA.jsonl")
    assert any(c.kind == "recital" for c in chunks)


def test_changed_text_fails_ingestion(
    corpus_settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    run(corpus_settings, "--update-lock")
    FakeCellar.payload = FakeCellar.payload.replace(b"Article 64", b"Article 65")
    assert run(corpus_settings, "--only", "DORA") == cli.EXIT_FAILED
    assert "DORA: sha256" in capsys.readouterr().err


def test_lock_dates_are_shown_rather_than_the_cache_date(corpus_settings: Settings) -> None:
    run(corpus_settings, "--update-lock")
    lock = read_lock(corpus_settings.corpus_lock_path)
    lock.texts["DORA"] = lock.texts["DORA"].model_copy(update={"downloaded_at": "2026-01-15"})
    write_lock(corpus_settings.corpus_lock_path, lock)
    assert run(corpus_settings, "--only", "DORA") == cli.EXIT_OK
    chunks = read_chunks(corpus_settings.corpus_dir / "DORA.jsonl")
    assert {c.retrieved_on for c in chunks} == {"2026-01-15"}


def test_download_failure_is_reported(
    corpus_settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    FakeCellar.fail = True
    assert run(corpus_settings, "--update-lock") == cli.EXIT_FAILED
    assert "HTTP 503" in capsys.readouterr().err
    assert FakeCellar.closed == 1
    assert not corpus_settings.corpus_lock_path.exists()


def test_unknown_code_is_a_usage_error(
    corpus_settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run(corpus_settings, "--only", "GDPR", "--update-lock") == cli.EXIT_USAGE
    assert "unknown regulation" in capsys.readouterr().err


def test_published_corpus_cannot_rewrite_the_lock(corpus_settings: Settings) -> None:
    args = ("--from-url", "https://example.org/corpus.jsonl", "--update-lock")
    assert run(corpus_settings, *args) == cli.EXIT_USAGE


def test_published_corpus_is_checked_against_the_lock(
    corpus_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    run(corpus_settings, "--update-lock")
    published = read_chunks(corpus_settings.corpus_dir / "DORA.jsonl")
    for path in corpus_settings.corpus_dir.iterdir():
        path.unlink()

    def fake_fetch(url: str, settings: Settings) -> list[Chunk]:
        assert url == "https://example.org/corpus.jsonl"
        return published

    monkeypatch.setattr(cli, "fetch_published_corpus", fake_fetch)
    url_args = ("--from-url", "https://example.org/corpus.jsonl")
    assert run(corpus_settings, *url_args, "--only", "DORA") == cli.EXIT_OK
    assert read_chunks(corpus_settings.corpus_dir / "DORA.jsonl") == published
    # The release only carries DORA here, so AIACT comes back with zero articles.
    assert run(corpus_settings, *url_args, "--only", "AIACT") == cli.EXIT_FAILED


def test_published_corpus_errors_are_reported(
    corpus_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    run(corpus_settings, "--update-lock")

    def broken(url: str, settings: Settings) -> list[Chunk]:
        raise RemoteCorpusError("HTTP 404 for the release asset")

    monkeypatch.setattr(cli, "fetch_published_corpus", broken)
    assert run(corpus_settings, "--from-url", "https://example.org/c.jsonl") == cli.EXIT_FAILED


def test_default_settings_are_used_when_none_are_given(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    cli.get_settings.cache_clear()
    try:
        assert cli.main(["--only", "DORA"]) == cli.EXIT_USAGE
    finally:
        cli.get_settings.cache_clear()
