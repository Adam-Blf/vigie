from pathlib import Path

import pytest

from vigie.corpus.lock import (
    CorpusLock,
    LockEntry,
    LockMismatchError,
    read_lock,
    sha256_hex,
    verify,
    write_lock,
)

ENTRY = LockEntry(celex="32022R2554", sha256="a" * 64, articles=64, downloaded_at="2026-10-02")


@pytest.fixture
def lock() -> CorpusLock:
    return CorpusLock(texts={"DORA": ENTRY})


def test_lock_round_trips_through_disk(tmp_path: Path, lock: CorpusLock) -> None:
    path = tmp_path / "nested" / "corpus.lock"
    lock.texts["AIACT"] = ENTRY.model_copy(update={"celex": "32024R1689"})
    write_lock(path, lock)
    loaded = read_lock(path)
    assert loaded == lock
    # Sorted keys keep the diff of the versioned file readable.
    assert list(loaded.texts) == ["AIACT", "DORA"]


def test_sha256_hex_is_the_standard_digest() -> None:
    assert sha256_hex(b"") == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def test_matching_text_passes(lock: CorpusLock) -> None:
    assert verify(lock, "DORA", celex="32022R2554", articles=64, sha256="a" * 64) == ENTRY


def test_every_difference_is_reported_at_once(lock: CorpusLock) -> None:
    with pytest.raises(LockMismatchError) as error:
        verify(lock, "DORA", celex="32022R9999", articles=63, sha256="b" * 64)
    message = str(error.value)
    assert "CELEX 32022R9999 instead of 32022R2554" in message
    assert "63 articles instead of 64" in message
    assert "sha256 bbbbbbbbbbbb instead of aaaaaaaaaaaa" in message


def test_published_jsonl_skips_the_hash_but_not_the_count(lock: CorpusLock) -> None:
    verify(lock, "DORA", celex="32022R2554", articles=64, sha256=None)
    with pytest.raises(LockMismatchError, match="63 articles"):
        verify(lock, "DORA", celex="32022R2554", articles=63, sha256=None)


def test_text_missing_from_the_lock_fails(lock: CorpusLock) -> None:
    with pytest.raises(LockMismatchError, match="AMLR: absent"):
        verify(lock, "AMLR", celex="32024R1624", articles=90, sha256="c" * 64)
