"""The HTTP routes. They stay thin: check access, then hand over to the ask service.

Handlers are plain functions, not coroutines: the RAG pipeline and the LLM clients are
synchronous, and FastAPI runs such handlers in its thread pool instead of blocking the
event loop for the tens of seconds a local generation can take.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse

from vigie.api.deps import Admin, State, User, admit
from vigie.api.errors import ApiError, trace_id_of
from vigie.api.schemas import (
    AdminUsageOut,
    AskRequest,
    AskResponse,
    DriftOut,
    ErrorOut,
    HealthOut,
    ReadyOut,
    UsageOut,
    ValidationErrorOut,
)
from vigie.api.service import AskService, Screened
from vigie.api.usage import UsageSummary

router = APIRouter()

_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorOut, "description": "Jeton absent, inconnu, expiré ou révoqué"},
    413: {"model": ErrorOut, "description": "Corps de requête au-delà de 16 Ko"},
    422: {"model": ValidationErrorOut, "description": "Question vide ou trop longue"},
    429: {"model": ErrorOut, "description": "Limite de débit ou quota quotidien atteint"},
    503: {"model": ErrorOut, "description": "Maintenance ou modèle saturé, voir Retry-After"},
}
_STREAM: dict[int | str, dict[str, Any]] = {
    200: {
        "description": "Flux text/event-stream : événements delta, puis answer ou error",
        "content": {"text/event-stream": {"schema": {"type": "string"}}},
    }
}


def _screen(state: State, principal: User, body: AskRequest) -> Screened:
    limit = state.settings.max_question_chars
    if len(body.question) > limit:
        # Same shape as the schema's own 2 000 character check, for a lower setting.
        error = {"loc": ("body", "question"), "msg": f"at most {limit} characters"}
        raise RequestValidationError([{**error, "type": "string_too_long"}])
    admit(state, principal)
    return AskService(state).screen(body.question)


@router.post("/v1/ask", response_model=AskResponse, responses=_ERRORS, tags=["questions"])
def ask(body: AskRequest, state: State, principal: User, request: Request) -> AskResponse:
    service = AskService(state)
    screened = _screen(state, principal, body)
    trace_id = trace_id_of(request)
    if screened.decision.blocked:
        return service.blocked(principal, screened, trace_id)
    service.reserve(principal, screened, trace_id)
    return service.answer(principal, screened, trace_id)


@router.post(
    "/v1/ask/stream",
    response_class=StreamingResponse,
    responses={**_ERRORS, **_STREAM},
    tags=["questions"],
)
def ask_stream(
    body: AskRequest, state: State, principal: User, request: Request
) -> StreamingResponse:
    service = AskService(state)
    screened = _screen(state, principal, body)
    trace_id = trace_id_of(request)
    headers = {"X-Accel-Buffering": "no"}
    if screened.decision.blocked:
        blocked = service.blocked(principal, screened, trace_id)
        events = iter([f"event: answer\ndata: {blocked.model_dump_json()}\n\n"])
        return StreamingResponse(events, media_type="text/event-stream", headers=headers)
    service.reserve(principal, screened, trace_id)
    return StreamingResponse(
        service.stream(principal, screened, trace_id),
        media_type="text/event-stream",
        headers=headers,
    )


def _usage(summary: UsageSummary, quota: int) -> UsageOut:
    return UsageOut(**vars(summary), daily_quota=quota)


@router.get("/v1/usage/me", response_model=UsageOut, responses=_ERRORS, tags=["usage"])
def usage_me(state: State, principal: User) -> UsageOut:
    return _usage(state.usage.summary(principal.user), state.settings.daily_quota)


@router.get("/v1/admin/usage", response_model=AdminUsageOut, responses=_ERRORS, tags=["admin"])
def admin_usage(state: State, principal: Admin) -> AdminUsageOut:
    quota = state.settings.daily_quota
    return AdminUsageOut(users=[_usage(s, quota) for s in state.usage.summaries()])


@router.get(
    "/v1/admin/drift",
    response_model=DriftOut,
    responses={**_ERRORS, 403: {"model": ErrorOut, "description": "Jeton sans portée admin"}},
    tags=["admin"],
)
def admin_drift(state: State, principal: Admin) -> DriftOut:
    if state.drift is None:
        # The reference was never built, so there is nothing to compare traffic against.
        raise ApiError(503, "drift_unavailable")
    return DriftOut.model_validate(state.drift.evaluate().to_dict())


@router.get("/healthz", response_model=HealthOut, tags=["ops"])
def healthz() -> HealthOut:
    return HealthOut(status="ok")


@router.get("/readyz", response_model=ReadyOut, responses={503: {"model": ReadyOut}}, tags=["ops"])
def readyz(state: State) -> JSONResponse:
    checks = {name: probe() for name, probe in state.probes.items()}
    ready = all(checks.values())
    body = ReadyOut(status="ready" if ready else "not_ready", checks=checks)
    return JSONResponse(body.model_dump(), status_code=200 if ready else 503)


@router.get("/metrics", include_in_schema=False)
def metrics(state: State) -> Response:
    # Served on the API port for now; Traefik only routes /v1 and / to the cluster, so
    # this path is not reachable from outside.
    return Response(state.metrics.render(), media_type="text/plain; version=0.0.4")
