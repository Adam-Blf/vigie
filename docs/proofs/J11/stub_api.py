"""Throwaway stand-in for POST /v1/ask, used only to check the Locust wiring before J5.

It is not the Vigie API: no retrieval, no LLM. It answers instantly, blocks prompts that
contain obvious injection markers and returns 401 without a vig_ bearer token. The real
measurement replaces it with the API once J5 is merged (see docs/load-test.md).
"""

from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MARKERS = ("ignore", "oublie", "developer mode", "répète", "pretend")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return

    def do_POST(self) -> None:  # noqa: N802 - name imposed by BaseHTTPRequestHandler
        auth = self.headers.get("Authorization", "")
        if self.path != "/v1/ask":
            self.send_response(404)
            self.end_headers()
            return
        if not auth.startswith("Bearer vig_"):
            self.send_response(401)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", "0"))
        question = json.loads(self.rfile.read(length))["question"].lower()
        blocked = any(marker in question for marker in MARKERS)
        body = json.dumps(
            {
                "answer": "" if blocked else "stub",
                "citations": [],
                "blocked": blocked,
                "block_reason": "injection" if blocked else None,
                "refused": False,
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1])), Handler).serve_forever()
