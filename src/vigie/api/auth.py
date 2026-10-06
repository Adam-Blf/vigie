"""Access tokens: creation, verification, listing, revocation.

A token is "vig_" followed by 32 random bytes in URL-safe base64. The prefix makes a
leaked token easy to spot for gitleaks and for a human. Only its SHA-256 is stored, so a
copy of the database opens nothing. Tokens expire after 30 days by default and carry one
scope, "user" or "admin".
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from vigie.api.db import connect, init_db

Scope = Literal["user", "admin"]
PREFIX = "vig_"
# token_urlsafe(32) gives 43 characters; the bounds reject junk before any hashing.
_MIN_LEN, _MAX_LEN = len(PREFIX) + 40, len(PREFIX) + 64

SCHEMA = """
CREATE TABLE IF NOT EXISTS tokens (
    id TEXT PRIMARY KEY,
    user TEXT NOT NULL,
    scope TEXT NOT NULL CHECK (scope IN ('user', 'admin')),
    token_hash TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    last_used_at TEXT,
    revoked_at TEXT
);
"""


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Principal:
    """Who is calling, as far as the API needs to know."""

    token_id: str
    user: str
    scope: Scope


@dataclass(frozen=True)
class TokenInfo:
    id: str
    user: str
    scope: Scope
    created_at: str
    expires_at: str
    last_used_at: str | None
    revoked_at: str | None


@dataclass(frozen=True)
class IssuedToken:
    info: TokenInfo
    # The clear token exists only here, once, for the command that prints it.
    secret: str


class TokenStore:
    def __init__(self, path: Path, ttl_days: int, clock: Callable[[], datetime] = utcnow) -> None:
        self._path = path
        self._ttl = timedelta(days=ttl_days)
        self._clock = clock
        init_db(path, SCHEMA)

    def create(self, user: str, scope: Scope = "user") -> IssuedToken:
        if not user.strip():
            raise ValueError("the user name must not be empty")
        secret = PREFIX + secrets.token_urlsafe(32)
        now = self._clock()
        info = TokenInfo(
            id=secrets.token_hex(6),
            user=user.strip(),
            scope=scope,
            created_at=now.isoformat(),
            expires_at=(now + self._ttl).isoformat(),
            last_used_at=None,
            revoked_at=None,
        )
        with connect(self._path) as conn:
            conn.execute(
                "INSERT INTO tokens (id, user, scope, token_hash, created_at, expires_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (info.id, info.user, scope, hash_token(secret), info.created_at, info.expires_at),
            )
        return IssuedToken(info, secret)

    def verify(self, presented: str) -> Principal | None:
        """Return the caller behind a token, or None if it is unknown, expired or revoked."""
        if not presented.startswith(PREFIX) or not _MIN_LEN <= len(presented) <= _MAX_LEN:
            return None
        digest = hash_token(presented)
        with connect(self._path) as conn:
            row = conn.execute(
                "SELECT id, user, scope, token_hash, expires_at, revoked_at"
                " FROM tokens WHERE token_hash = ?",
                (digest,),
            ).fetchone()
            # The lookup is on a SHA-256, which a caller cannot steer byte by byte; the
            # constant-time comparison still guards the final equality.
            if row is None or not hmac.compare_digest(row["token_hash"], digest):
                return None
            now = self._clock()
            if row["revoked_at"] is not None or datetime.fromisoformat(row["expires_at"]) <= now:
                return None
            conn.execute(
                "UPDATE tokens SET last_used_at = ? WHERE id = ?", (now.isoformat(), row["id"])
            )
        return Principal(token_id=row["id"], user=row["user"], scope=row["scope"])

    def list_tokens(self) -> list[TokenInfo]:
        with connect(self._path) as conn:
            rows = conn.execute(
                "SELECT id, user, scope, created_at, expires_at, last_used_at, revoked_at"
                " FROM tokens ORDER BY created_at"
            ).fetchall()
        return [TokenInfo(**dict(row)) for row in rows]

    def revoke(self, token_id: str) -> bool:
        with connect(self._path) as conn:
            cursor = conn.execute(
                "UPDATE tokens SET revoked_at = ? WHERE id = ? AND revoked_at IS NULL",
                (self._clock().isoformat(), token_id),
            )
        return cursor.rowcount == 1

    def rotate_admin(self, user: str) -> tuple[IssuedToken, int]:
        """Revoke every live admin token, then issue a fresh one. Returns it and the count."""
        with connect(self._path) as conn:
            cursor = conn.execute(
                "UPDATE tokens SET revoked_at = ? WHERE scope = 'admin' AND revoked_at IS NULL",
                (self._clock().isoformat(),),
            )
        return self.create(user, scope="admin"), cursor.rowcount
