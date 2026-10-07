"""Retention of the usage counters and token rows (privacy page: 12 months)."""

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from vigie.api.auth import TokenStore
from vigie.api.usage import UsageEvent, UsageStore
from vigie.config import Settings


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 10, 7, 9, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now


def usage_days(db: Path) -> list[str]:
    with sqlite3.connect(db) as conn:
        return [row[0] for row in conn.execute("SELECT day FROM usage ORDER BY day")]


def token_ids(db: Path) -> set[str]:
    with sqlite3.connect(db) as conn:
        return {row[0] for row in conn.execute("SELECT id FROM tokens")}


def test_usage_rows_older_than_the_retention_are_deleted(tmp_path: Path) -> None:
    db, clock = tmp_path / "u.sqlite3", Clock()
    store = UsageStore(db, 0.0, retention_days=365, clock=clock)
    store.record(UsageEvent("alice", "t1", status=200, latency_ms=1.0))
    clock.now += timedelta(days=200)
    store.record(UsageEvent("alice", "t1", status=200, latency_ms=1.0))
    clock.now += timedelta(days=200)
    store.record(UsageEvent("alice", "t1", status=200, latency_ms=1.0))
    # The first row is 400 days old, the second 200: only the first goes.
    assert usage_days(db) == ["2027-04-25", "2027-11-11"]


def test_usage_purge_runs_once_a_day(tmp_path: Path) -> None:
    db, clock = tmp_path / "u.sqlite3", Clock()
    store = UsageStore(db, 0.0, retention_days=1, clock=clock)
    store.record(UsageEvent("alice", "t1", status=200, latency_ms=1.0))
    clock.now += timedelta(days=3)
    assert store.purge() == 1
    assert store.purge() == 0


def test_dead_tokens_are_forgotten_after_the_retention(tmp_path: Path) -> None:
    db, clock = tmp_path / "v.sqlite3", Clock()
    store = TokenStore(db, ttl_days=30, retention_days=365, clock=clock)
    revoked = store.create("alice")
    expired = store.create("bob")
    live = store.create("carol")
    store.revoke(revoked.info.id)
    clock.now += timedelta(days=380)
    renewed = store.create("carol")
    # Revoked 380 days ago, expired 350 days ago: only the revoked row is past 365 days.
    assert store.purge() == 1
    assert token_ids(db) == {expired.info.id, live.info.id, renewed.info.id}
    assert store.verify(renewed.secret) is not None


def test_verify_triggers_the_daily_token_purge(tmp_path: Path) -> None:
    db, clock = tmp_path / "v.sqlite3", Clock()
    store = TokenStore(db, ttl_days=1, retention_days=1, clock=clock)
    old = store.create("alice")
    clock.now += timedelta(days=5)
    store.verify(old.secret)
    assert token_ids(db) == set()


def test_settings_default_to_twelve_months() -> None:
    assert Settings().usage_retention_days == 365
