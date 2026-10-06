"""Request dependencies: who is calling, and may they ask one more question now.

Authentication answers 401 for every failure (missing header, unknown, expired or
revoked token) with the same body, so a caller cannot tell a revoked token from a typo.
Scope failures answer 403: the token is real, the route is just not for it.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from vigie.api.auth import Principal
from vigie.api.errors import ApiError, retry_later, unauthorized
from vigie.api.state import AppState
from vigie.api.usage import seconds_until_tomorrow, utcnow

bearer = HTTPBearer(auto_error=False, description="Jeton Vigie `vig_...`")


def get_state(request: Request) -> AppState:
    state: AppState = request.app.state.vigie
    return state


State = Annotated[AppState, Depends(get_state)]


def current_principal(
    state: State,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> Principal:
    if credentials is None:
        raise unauthorized()
    principal = state.tokens.verify(credentials.credentials)
    if principal is None:
        raise unauthorized()
    return principal


User = Annotated[Principal, Depends(current_principal)]


def admin_principal(principal: User) -> Principal:
    if principal.scope != "admin":
        raise ApiError(403, "forbidden")
    return principal


Admin = Annotated[Principal, Depends(admin_principal)]


def admit(state: AppState, principal: Principal) -> None:
    """Apply the per-minute limit, then the daily quota of the token.

    Refused requests are not recorded as usage: otherwise a client hammering the API
    after its quota would keep pushing its own reset further away.
    """
    wait = state.limiter.acquire(principal.token_id)
    if wait is not None:
        raise retry_later(429, "rate_limited", wait)
    if state.usage.count_today(principal.token_id) >= state.settings.daily_quota:
        raise retry_later(429, "quota_exceeded", seconds_until_tomorrow(utcnow()))
