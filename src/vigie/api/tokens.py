"""Token administration from the command line.

    python -m vigie.api.tokens create <user> [--scope user|admin]
    python -m vigie.api.tokens list
    python -m vigie.api.tokens revoke <token-id>
    python -m vigie.api.tokens rotate-admin <user>

A new token is printed once, on its own line, and never again: only its hash is stored.
The listing shows ids, owners, scopes and dates, never a token or a hash.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from typing import TextIO

from vigie.api.auth import IssuedToken, TokenStore
from vigie.config import get_settings


def _store() -> TokenStore:
    settings = get_settings()
    return TokenStore(settings.db_path, settings.token_ttl_days)


def _print_issued(issued: IssuedToken, out: TextIO) -> None:
    info = issued.info
    out.write(f"id={info.id} user={info.user} scope={info.scope} expires={info.expires_at}\n")
    out.write("Copy the token now, it will not be shown again:\n")
    out.write(f"{issued.secret}\n")


def main(argv: Sequence[str] | None = None, out: TextIO = sys.stdout) -> int:
    parser = argparse.ArgumentParser(prog="python -m vigie.api.tokens", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create", help="issue a token")
    create.add_argument("user")
    create.add_argument("--scope", choices=["user", "admin"], default="user")
    commands.add_parser("list", help="list tokens without their secrets")
    revoke = commands.add_parser("revoke", help="revoke a token by id")
    revoke.add_argument("token_id")
    rotate = commands.add_parser("rotate-admin", help="revoke all admin tokens, issue one")
    rotate.add_argument("user")
    args = parser.parse_args(argv)

    store = _store()
    if args.command == "create":
        _print_issued(store.create(args.user, args.scope), out)
    elif args.command == "list":
        for t in store.list_tokens():
            state = "revoked" if t.revoked_at else "active"
            out.write(
                f"{t.id}  {t.user}  {t.scope}  {state}  created={t.created_at}"
                f"  expires={t.expires_at}  last_used={t.last_used_at or '-'}\n"
            )
    elif args.command == "revoke":
        if not store.revoke(args.token_id):
            out.write(f"no active token with id {args.token_id}\n")
            return 1
        out.write(f"revoked {args.token_id}\n")
    else:
        issued, revoked = store.rotate_admin(args.user)
        out.write(f"revoked {revoked} admin token(s)\n")
        _print_issued(issued, out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
