"""The outer layer every request crosses, before any route runs.

Written as a plain ASGI middleware rather than with BaseHTTPMiddleware, because it must
see the raw body (to cut it at 16 KB before FastAPI parses anything) and must not buffer
the server-sent event stream of /v1/ask/stream.

In order: a trace id, the maintenance switch, the body limit, then on the way out the
security and version headers and the request metrics.
"""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any

from vigie.api.state import AppState

Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]

SECURITY_HEADERS = {
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
    "x-frame-options": "DENY",
    # The API serves JSON and events only, so nothing may load or frame it.
    "content-security-policy": "default-src 'none'; frame-ancestors 'none'",
    "cross-origin-opener-policy": "same-origin",
    "cross-origin-resource-policy": "same-origin",
    "permissions-policy": "camera=(), microphone=(), geolocation=()",
    "cache-control": "no-store",
}


class VigieMiddleware:
    def __init__(self, app: ASGIApp, state: AppState, routes: frozenset[str]) -> None:
        self._app = app
        self._state = state
        # Only known paths become metric labels; a scan of random URLs must not create
        # one series per URL.
        self._routes = routes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        trace_id = uuid.uuid4().hex
        scope.setdefault("state", {})["trace_id"] = trace_id
        path: str = scope["path"]
        route = path if path in self._routes else "unmatched"
        start = time.perf_counter()
        status_seen = 500

        async def send_with_headers(message: Message) -> None:
            nonlocal status_seen
            if message["type"] == "http.response.start":
                status_seen = message["status"]
                headers = list(message.get("headers", []))
                headers.extend((k.encode(), v.encode()) for k, v in self._headers(trace_id))
                message["headers"] = headers
            await send(message)

        try:
            if self._state.settings.maintenance and (path.startswith("/v1") or path == "/readyz"):
                await self._reject(send_with_headers, 503, "maintenance", trace_id, retry=True)
                return
            replay = await self._read_body(scope, receive)
            if replay is None:
                await self._reject(send_with_headers, 413, "payload_too_large", trace_id)
                return
            await self._app(scope, replay, send_with_headers)
        finally:
            self._observe(route, status_seen, time.perf_counter() - start)

    def _headers(self, trace_id: str) -> list[tuple[str, str]]:
        s = self._state
        return [
            *SECURITY_HEADERS.items(),
            ("x-trace-id", trace_id),
            ("x-app-version", s.settings.app_version),
            ("x-bundle-version", s.bundle.bundle_version),
            ("x-prompt-version", s.bundle.prompt_version),
        ]

    def _observe(self, route: str, status: int, seconds: float) -> None:
        metrics = self._state.metrics
        metrics.requests.labels(metrics.bundle_version, route, str(status)).inc()
        metrics.latency.labels(metrics.bundle_version, route).observe(seconds)

    async def _read_body(self, scope: Scope, receive: Receive) -> Receive | None:
        """Buffer the body up to the limit; None means it is too large."""
        limit = self._state.settings.max_body_bytes
        for name, value in scope.get("headers", []):
            if name == b"content-length" and value.isdigit() and int(value) > limit:
                return None
        chunks: list[bytes] = []
        size = 0
        while True:
            message = await receive()
            if message["type"] != "http.request":
                break  # client went away; let the app see the disconnect itself
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > limit:
                return None
            chunks.append(chunk)
            if not message.get("more_body", False):
                break
        body = b"".join(chunks)
        sent = False

        async def replay() -> Message:
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        return replay

    async def _reject(
        self, send: Send, status: int, code: str, trace_id: str, retry: bool = False
    ) -> None:
        body = json.dumps({"error": code, "trace_id": trace_id}).encode()
        headers = [(b"content-type", b"application/json"), (b"content-length", b"%d" % len(body))]
        if retry:
            headers.append((b"retry-after", str(self._state.settings.retry_after_s).encode()))
        await send({"type": "http.response.start", "status": status, "headers": headers})
        await send({"type": "http.response.body", "body": body})
