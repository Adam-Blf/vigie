import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from api_fixtures import make_api
from vigie.api.usage import UsageEvent, UsageStore, seconds_until_tomorrow


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 10, 6, 23, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now


def event(user: str = "alice", key: str = "t1", **kw: object) -> UsageEvent:
    values: dict[str, object] = {"status": 200, "latency_ms": 12.34, "tokens_in": 600}
    values.update(kw)
    return UsageEvent(user=user, token_id=key, **values)  # type: ignore[arg-type]


def test_summary_totals_and_cost(tmp_path: Path) -> None:
    store = UsageStore(tmp_path / "u.sqlite3", cost_per_1k_tokens_eur=0.5)
    store.record(event(tokens_out=400))
    store.record(event(blocked=True, tokens_in=0))
    store.record(event(refused=True, tokens_in=0))
    summary = store.summary("alice")
    assert (summary.requests, summary.blocked, summary.refused) == (3, 1, 1)
    assert (summary.tokens_in, summary.tokens_out) == (600, 400)
    assert summary.cost_eur == 0.5


def test_unknown_user_has_an_empty_summary(tmp_path: Path) -> None:
    store = UsageStore(tmp_path / "u.sqlite3", 0.0)
    assert store.summary("nobody").requests == 0


def test_daily_count_is_per_token_and_resets_at_midnight(tmp_path: Path) -> None:
    clock = Clock()
    store = UsageStore(tmp_path / "u.sqlite3", 0.0, clock=clock)
    store.record(event(key="t1"))
    store.record(event(key="t2"))
    assert store.count_today("t1") == 1
    clock.now += timedelta(hours=2)
    assert store.count_today("t1") == 0
    assert store.summary("alice").requests_today == 0


def test_no_question_text_column(tmp_path: Path) -> None:
    store = UsageStore(tmp_path / "u.sqlite3", 0.0)
    store.record(event())
    import sqlite3

    with sqlite3.connect(tmp_path / "u.sqlite3") as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(usage)")}
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert not columns & {"question", "answer", "text"}
    assert mode == "wal"


def test_three_replicas_writing_at_once_lose_nothing(tmp_path: Path) -> None:
    path = tmp_path / "shared.sqlite3"
    replicas = [UsageStore(path, 0.0) for _ in range(3)]

    def hammer(store: UsageStore) -> None:
        for _ in range(40):
            store.record(event())

    threads = [threading.Thread(target=hammer, args=(store,)) for store in replicas]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert replicas[0].summary("alice").requests == 120


def test_seconds_until_tomorrow() -> None:
    late = datetime(2026, 10, 6, 23, 59, 30, tzinfo=timezone.utc)
    assert seconds_until_tomorrow(late) == 30
    assert seconds_until_tomorrow(late.replace(hour=0, minute=0, second=0)) == 86400


def test_usage_me_reports_own_numbers_only(tmp_path: Path) -> None:
    api = make_api(tmp_path, daily_quota=50)
    api.ask()
    api.client.post("/v1/ask", json={"question": "DORA ?"}, headers=api.auth(api.admin_token))
    body = api.client.get("/v1/usage/me", headers=api.auth()).json()
    assert body["user"] == "alice" and body["requests"] == 1
    assert body["daily_quota"] == 50
    assert set(body) == {
        "user",
        "requests",
        "blocked",
        "refused",
        "tokens_in",
        "tokens_out",
        "cost_eur",
        "requests_today",
        "daily_quota",
    }
