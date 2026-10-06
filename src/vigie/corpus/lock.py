"""data/corpus.lock pins the exact official text every answer is built on.

If the Publications Office republishes a consolidated version, the hash moves and ingestion
stops instead of quietly mixing two versions of the law in one index.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from pydantic import BaseModel, ConfigDict

LOCK_VERSION = 1


class LockMismatchError(RuntimeError):
    """The downloaded corpus is not the one the lock file promises."""


class LockEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    celex: str
    sha256: str
    articles: int
    downloaded_at: str


class CorpusLock(BaseModel):
    version: int = LOCK_VERSION
    texts: dict[str, LockEntry] = {}


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_lock(path: Path) -> CorpusLock:
    return CorpusLock.model_validate_json(path.read_text(encoding="utf-8"))


def write_lock(path: Path, lock: CorpusLock) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = CorpusLock(version=lock.version, texts=dict(sorted(lock.texts.items())))
    path.write_text(ordered.model_dump_json(indent=2) + "\n", encoding="utf-8")


def verify(
    lock: CorpusLock, code: str, *, celex: str, articles: int, sha256: str | None
) -> LockEntry:
    """Raise with every difference at once, so one run tells the whole story.

    `sha256` is None when the chunks come from a published JSONL rather than the XHTML: the
    article count and the CELEX number are then the only things left to compare.
    """
    entry = lock.texts.get(code)
    if entry is None:
        raise LockMismatchError(f"{code}: absent from the lock file")
    problems: list[str] = []
    if entry.celex != celex:
        problems.append(f"CELEX {celex} instead of {entry.celex}")
    if entry.articles != articles:
        problems.append(f"{articles} articles instead of {entry.articles}")
    if sha256 is not None and entry.sha256 != sha256:
        problems.append(f"sha256 {sha256[:12]} instead of {entry.sha256[:12]}")
    if problems:
        raise LockMismatchError(f"{code}: " + ", ".join(problems))
    return entry
