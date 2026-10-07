"""Builds the FastAPI application around an AppState.

The interactive documentation and the live /openapi.json are switched off: the contract
is published in docs/openapi.json, generated from the same routes, and an API that lists
its own routes to anyone only helps a scanner.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from vigie.api import errors
from vigie.api.middleware import VigieMiddleware
from vigie.api.routes import router
from vigie.api.schemas import CONTRACT_VERSION
from vigie.api.state import AppState

EXPOSED_HEADERS = [
    "Retry-After",
    "X-Trace-Id",
    "X-App-Version",
    "X-Bundle-Version",
    "X-AI-Generated",
]

Lifespan = Callable[[FastAPI], AbstractAsyncContextManager[None]]


def base_app(lifespan: Lifespan | None = None) -> FastAPI:
    """Routes and error handlers only; enough to generate the contract without a state."""
    app = FastAPI(
        title="Vigie API",
        version=CONTRACT_VERSION,
        summary="Réponses citées sur DORA, l'AI Act, le RGPD et l'AMLR.",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    errors.register(app)
    app.include_router(router)
    return app


def create_app(state: AppState) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        for close in state.on_close:
            close()

    app = base_app(lifespan)
    app.state.vigie = state
    # In production the interface and the API share one origin, so CORS only matters
    # for the local interface on its own port.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=state.settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
        expose_headers=EXPOSED_HEADERS,
        allow_credentials=False,
    )
    routes = frozenset(str(getattr(route, "path", "")) for route in router.routes) - {""}
    # Added last, so it runs first: maintenance and the body limit come before CORS.
    app.add_middleware(VigieMiddleware, state=state, routes=routes)
    return app
