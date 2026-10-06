"""The AI Act audit log: what was asked, what was answered, and what the guards decided.

It is the only place where question text is kept, so the rules are strict. No IP address
and no User-Agent are written; obvious personal data is masked before the line exists;
lines older than the retention period (30 days by default) are deleted day by day.

Each line carries the hash of the previous one, so editing or removing a line in the
middle breaks the chain and verify() says where. Every pod writes its own files: two
writers appending to one chain would fork it.
"""

from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

GENESIS = "0" * 64


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _canonical(entry: Mapping[str, Any]) -> bytes:
    return json.dumps(entry, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def chain_hash(entry: Mapping[str, Any]) -> str:
    """Hash of a line without its own hash field; the previous hash is part of it."""
    body = {key: value for key, value in entry.items() if key != "hash"}
    return hashlib.sha256(_canonical(body)).hexdigest()


@dataclass(frozen=True)
class ChainReport:
    ok: bool
    lines: int
    error: str | None = None


class AuditLog:
    def __init__(
        self,
        root: Path,
        pod: str,
        retention_days: int,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        self._dir = root / pod
        self._retention = timedelta(days=retention_days)
        self._clock = clock
        self._lock = threading.Lock()
        self._dir.mkdir(parents=True, exist_ok=True)
        self._last_hash = self._read_last_hash()
        self._purged_on: date | None = None

    @property
    def directory(self) -> Path:
        return self._dir

    def _files(self) -> list[Path]:
        return sorted(self._dir.glob("*.jsonl"))

    def _read_last_hash(self) -> str:
        for path in reversed(self._files()):
            lines = path.read_text(encoding="utf-8").splitlines()
            if lines:
                last: str = json.loads(lines[-1])["hash"]
                return last
        return GENESIS

    def write(self, record: Mapping[str, Any]) -> str:
        """Append one line and return its hash."""
        now = self._clock()
        with self._lock:
            if self._purged_on != now.date():
                # Purging on the first write of each day keeps retention automatic
                # without a scheduler inside the pod.
                self._purge_locked(now)
                self._purged_on = now.date()
            entry = {"ts": now.isoformat(), **record, "prev": self._last_hash}
            entry["hash"] = chain_hash(entry)
            path = self._dir / f"{now.date().isoformat()}.jsonl"
            with path.open("a", encoding="utf-8") as handle:
                handle.write(_canonical(entry).decode() + "\n")
            self._last_hash = entry["hash"]
        return str(entry["hash"])

    def purge(self) -> list[Path]:
        with self._lock:
            return self._purge_locked(self._clock())

    def _purge_locked(self, now: datetime) -> list[Path]:
        cutoff = (now - self._retention).date()
        removed = []
        for path in self._files():
            try:
                day = date.fromisoformat(path.stem)
            except ValueError:
                continue  # not one of ours, leave it alone
            if day < cutoff:
                path.unlink()
                removed.append(path)
        return removed


def verify_chain(directory: Path) -> ChainReport:
    """Check every line of one pod's files, oldest first.

    The first remaining line may point to a hash that was purged; that is the normal
    effect of retention, so it is accepted as the anchor. Any later break is an error.
    """
    previous: str | None = None
    count = 0
    for path in sorted(directory.glob("*.jsonl")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            where = f"{path.name}:{number}"
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                return ChainReport(False, count, f"{where} is not valid JSON")
            if entry.get("hash") != chain_hash(entry):
                return ChainReport(False, count, f"{where} was modified")
            if previous is not None and entry.get("prev") != previous:
                return ChainReport(False, count, f"{where} does not follow the line before it")
            previous = entry["hash"]
            count += 1
    return ChainReport(True, count)
