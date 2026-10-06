"""Usage tracking: one row per answered request, no question text.

The table answers three needs: the user's own page (/v1/usage/me), the daily quota of a
token, and the administrator's overview. The text of a question is deliberately absent;
it lives only in the audit log, which has its own retention and masking rules.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from vigie.api.db import connect, init_db

SCHEMA = """
CREATE TABLE IF NOT EXISTS usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user TEXT NOT NULL,
    token_id TEXT NOT NULL,
    ts TEXT NOT NULL,
    day TEXT NOT NULL,
    status INTEGER NOT NULL,
    latency_ms REAL NOT NULL,
    tokens_in INTEGER NOT NULL,
    tokens_out INTEGER NOT NULL,
    cost_eur REAL NOT NULL,
    blocked INTEGER NOT NULL,
    refused INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS usage_token_day ON usage (token_id, day);
CREATE INDEX IF NOT EXISTS usage_user ON usage (user);
"""


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class UsageEvent:
    user: str
    token_id: str
    status: int
    latency_ms: float
    tokens_in: int = 0
    tokens_out: int = 0
    blocked: bool = False
    refused: bool = False


@dataclass(frozen=True)
class UsageSummary:
    user: str
    requests: int
    blocked: int
    refused: int
    tokens_in: int
    tokens_out: int
    cost_eur: float
    requests_today: int


def seconds_until_tomorrow(now: datetime) -> int:
    """Quotas reset at midnight UTC; this is the Retry-After of an exhausted quota."""
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(1, int((tomorrow - now).total_seconds()))


class UsageStore:
    def __init__(
        self,
        path: Path,
        cost_per_1k_tokens_eur: float,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        self._path = path
        self._price = cost_per_1k_tokens_eur
        self._clock = clock
        init_db(path, SCHEMA)

    def record(self, event: UsageEvent) -> None:
        now = self._clock()
        cost = (event.tokens_in + event.tokens_out) / 1000 * self._price
        with connect(self._path) as conn:
            conn.execute(
                "INSERT INTO usage (user, token_id, ts, day, status, latency_ms, tokens_in,"
                " tokens_out, cost_eur, blocked, refused) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    event.user,
                    event.token_id,
                    now.isoformat(),
                    now.date().isoformat(),
                    event.status,
                    round(event.latency_ms, 1),
                    event.tokens_in,
                    event.tokens_out,
                    cost,
                    int(event.blocked),
                    int(event.refused),
                ),
            )

    def count_today(self, token_id: str) -> int:
        today = self._clock().date().isoformat()
        with connect(self._path) as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM usage WHERE token_id = ? AND day = ?", (token_id, today)
            ).fetchone()
        return int(row[0])

    def summaries(self, user: str | None = None) -> list[UsageSummary]:
        """Totals per user, for one user (their own page) or for all (administration)."""
        today = self._clock().date().isoformat()
        with connect(self._path) as conn:
            rows = conn.execute(
                "SELECT user, COUNT(*) AS requests, SUM(blocked) AS blocked,"
                " SUM(refused) AS refused, SUM(tokens_in) AS tokens_in,"
                " SUM(tokens_out) AS tokens_out, SUM(cost_eur) AS cost_eur,"
                " SUM(day = ?) AS requests_today"
                " FROM usage WHERE ? IS NULL OR user = ? GROUP BY user ORDER BY user",
                (today, user, user),
            ).fetchall()
        return [
            UsageSummary(
                user=row["user"],
                requests=row["requests"],
                blocked=row["blocked"],
                refused=row["refused"],
                tokens_in=row["tokens_in"],
                tokens_out=row["tokens_out"],
                cost_eur=round(row["cost_eur"], 6),
                requests_today=row["requests_today"],
            )
            for row in rows
        ]

    def summary(self, user: str) -> UsageSummary:
        found = self.summaries(user)
        return found[0] if found else UsageSummary(user, 0, 0, 0, 0, 0, 0.0, 0)
