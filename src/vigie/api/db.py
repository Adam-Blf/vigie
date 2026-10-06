"""SQLite connections for the token and usage tables.

WAL mode lets the API pods read while one of them writes, which is what a single volume
shared by up to three replicas needs. Each call opens its own short connection: SQLite
connections must not cross threads, and FastAPI runs synchronous handlers in a pool.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

# A writer waits this long for the lock before giving up, instead of failing at once
# when another replica happens to be committing.
BUSY_TIMEOUT_MS = 5000


def init_db(path: Path, schema: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as conn:
        # WAL is a property of the file, set once and kept by every later connection.
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(schema)


@contextmanager
def connect(path: Path) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(path, timeout=BUSY_TIMEOUT_MS / 1000)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
        with conn:
            yield conn
    finally:
        conn.close()
