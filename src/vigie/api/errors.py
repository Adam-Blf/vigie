"""Errors the API returns, always in the same small shape.

A client gets a stable code and the trace id of its request, never a message from deep
inside the stack: exception texts can carry paths, hosts or pieces of the question. The
details go to the server log, which the redaction filter guards.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from vigie.api.schemas import ErrorOut, FieldError, ValidationErrorOut

log = logging.getLogger("vigie.api")

_HTTP_CODES = {400: "bad_request", 404: "not_found", 405: "method_not_allowed"}


class ApiError(Exception):
    def __init__(self, status: int, code: str, headers: dict[str, str] | None = None) -> None:
        super().__init__(code)
        self.status = status
        self.code = code
        self.headers = headers or {}


def unauthorized() -> ApiError:
    return ApiError(401, "unauthorized", {"WWW-Authenticate": "Bearer"})


def retry_later(status: int, code: str, seconds: int) -> ApiError:
    return ApiError(status, code, {"Retry-After": str(seconds)})


def trace_id_of(request: Request) -> str:
    return str(getattr(request.state, "trace_id", ""))


def error_response(
    request: Request, status: int, code: str, headers: dict[str, str] | None = None
) -> JSONResponse:
    body = ErrorOut(error=code, trace_id=trace_id_of(request))
    return JSONResponse(body.model_dump(), status_code=status, headers=headers)


async def _api_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ApiError)  # noqa: S101 - registered for ApiError only
    return error_response(request, exc.status, exc.code, exc.headers)


async def _validation_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)  # noqa: S101 - registered for it only
    # FastAPI's default body echoes the rejected input, which here is the question.
    detail = [
        FieldError(loc=list(err.get("loc", ())), msg=str(err.get("msg", "")), type=err["type"])
        for err in exc.errors()
    ]
    body = ValidationErrorOut(error="invalid_request", trace_id=trace_id_of(request), detail=detail)
    return JSONResponse(jsonable_encoder(body), status_code=422)


async def _http_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)  # noqa: S101 - registered for it only
    code = _HTTP_CODES.get(exc.status_code, "http_error")
    return error_response(request, exc.status_code, code, dict(exc.headers or {}))


async def _unexpected(request: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled error, trace_id=%s", trace_id_of(request))
    return error_response(request, 500, "internal_error")


def register(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, _api_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(Exception, _unexpected)
