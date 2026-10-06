from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from api_fixtures import make_api
from vigie.api.auth import PREFIX, TokenStore, hash_token


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now


def test_missing_token_gives_401_with_bearer_challenge(tmp_path: Path) -> None:
    api = make_api(tmp_path)
    response = api.client.post("/v1/ask", json={"question": "Bonjour"})
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json() == {"error": "unauthorized", "trace_id": response.headers["x-trace-id"]}


@pytest.mark.parametrize(
    "header",
    [
        "Bearer vig_" + "x" * 43,  # well formed, unknown
        "Bearer not-a-vigie-token",
        "Bearer vig_short",
        "Basic dXNlcjpwYXNz",
        "Bearer",
    ],
)
def test_invalid_tokens_give_401(tmp_path: Path, header: str) -> None:
    api = make_api(tmp_path)
    response = api.client.get("/v1/usage/me", headers={"Authorization": header})
    assert response.status_code == 401
    assert response.json()["error"] == "unauthorized"


def test_valid_token_gives_200(tmp_path: Path) -> None:
    api = make_api(tmp_path)
    assert api.client.get("/v1/usage/me", headers=api.auth()).status_code == 200


def test_revoked_token_gives_401(tmp_path: Path) -> None:
    api = make_api(tmp_path)
    token_id = api.state.tokens.verify(api.user_token).token_id  # type: ignore[union-attr]
    assert api.state.tokens.revoke(token_id)
    assert api.client.get("/v1/usage/me", headers=api.auth()).status_code == 401


def test_expired_token_gives_401(tmp_path: Path) -> None:
    api = make_api(tmp_path)
    clock = Clock()
    store = TokenStore(api.state.settings.db_path, ttl_days=30, clock=clock)
    issued = store.create("bob")
    clock.now += timedelta(days=30)
    assert store.verify(issued.secret) is None
    # And through HTTP, with the app's own store reading the same expired row.
    api.state.tokens = store
    assert api.client.get("/v1/usage/me", headers=api.auth(issued.secret)).status_code == 401


def test_user_token_on_admin_route_gives_403(tmp_path: Path) -> None:
    api = make_api(tmp_path)
    response = api.client.get("/v1/admin/usage", headers=api.auth())
    assert response.status_code == 403
    assert response.json()["error"] == "forbidden"


def test_admin_token_reads_admin_route(tmp_path: Path) -> None:
    api = make_api(tmp_path)
    api.ask()
    response = api.client.get("/v1/admin/usage", headers=api.auth(api.admin_token))
    assert response.status_code == 200
    assert [row["user"] for row in response.json()["users"]] == ["alice"]


def test_tokens_are_prefixed_random_and_stored_hashed(tmp_path: Path) -> None:
    store = TokenStore(tmp_path / "t.sqlite3", ttl_days=30)
    first, second = store.create("a"), store.create("a")
    assert first.secret.startswith(PREFIX) and first.secret != second.secret
    assert len(first.secret) == len(PREFIX) + 43
    raw = (tmp_path / "t.sqlite3").read_bytes()
    assert first.secret.encode() not in raw
    assert hash_token(first.secret).encode() in raw


def test_verify_tracks_last_use_and_scope(tmp_path: Path) -> None:
    clock = Clock()
    store = TokenStore(tmp_path / "t.sqlite3", ttl_days=30, clock=clock)
    issued = store.create(" carol ", scope="admin")
    principal = store.verify(issued.secret)
    assert principal is not None
    assert (principal.user, principal.scope) == ("carol", "admin")
    [info] = store.list_tokens()
    assert info.last_used_at == clock.now.isoformat()
    assert info.expires_at == (clock.now + timedelta(days=30)).isoformat()


def test_empty_user_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="empty"):
        TokenStore(tmp_path / "t.sqlite3", ttl_days=30).create("  ")


def test_revoke_twice_reports_nothing_to_revoke(tmp_path: Path) -> None:
    store = TokenStore(tmp_path / "t.sqlite3", ttl_days=30)
    token_id = store.create("a").info.id
    assert store.revoke(token_id) is True
    assert store.revoke(token_id) is False


def test_rotate_admin_revokes_every_admin_token(tmp_path: Path) -> None:
    store = TokenStore(tmp_path / "t.sqlite3", ttl_days=30)
    old_admin = store.create("root", scope="admin")
    user = store.create("alice")
    fresh, revoked = store.rotate_admin("root")
    assert revoked == 1
    assert store.verify(old_admin.secret) is None
    assert store.verify(user.secret) is not None
    assert store.verify(fresh.secret) is not None
