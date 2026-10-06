import io
import re
from collections.abc import Iterator
from pathlib import Path

import pytest

from vigie.api import tokens
from vigie.api.auth import TokenStore
from vigie.config import get_settings


@pytest.fixture
def db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    path = tmp_path / "vigie.sqlite3"
    monkeypatch.setenv("VIGIE_DB_PATH", str(path))
    get_settings.cache_clear()
    yield path
    get_settings.cache_clear()


def run(*args: str) -> tuple[int, str]:
    out = io.StringIO()
    return tokens.main(list(args), out=out), out.getvalue()


def secret_of(output: str) -> str:
    return re.findall(r"^vig_\S+$", output, re.MULTILINE)[0]


def test_create_prints_the_token_once_and_list_never_shows_it(db: Path) -> None:
    code, out = run("create", "alice")
    assert code == 0 and "scope=user" in out
    secret = secret_of(out)
    assert TokenStore(db, 30).verify(secret) is not None
    code, listing = run("list")
    assert code == 0 and "alice  user  active" in listing
    assert "vig_" not in listing


def test_revoke_then_revoke_again(db: Path) -> None:
    _, out = run("create", "bob", "--scope", "admin")
    token_id = re.findall(r"id=(\w+)", out)[0]
    assert run("revoke", token_id) == (0, f"revoked {token_id}\n")
    assert run("revoke", token_id)[0] == 1
    assert "revoked" in run("list")[1]


def test_rotate_admin_replaces_admin_tokens(db: Path) -> None:
    _, first = run("create", "root", "--scope", "admin")
    code, out = run("rotate-admin", "root")
    assert code == 0 and out.startswith("revoked 1 admin token(s)")
    store = TokenStore(db, 30)
    assert store.verify(secret_of(first)) is None
    assert store.verify(secret_of(out)) is not None
