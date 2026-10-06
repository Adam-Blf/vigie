"""Stand-in for POST /v1/ask, used only to prove the replay and the gate before J5 exists.

It honours the response contract (answer, blocked, block_reason, refused) and has two modes:
- guarded: a crude keyword guard blocks or refuses, the way the real chain is expected to;
- leaky: nothing is blocked and the answer echoes a fake system prompt plus a fake e-mail,
  which must turn the gate red.

Run: python docs/proofs/J10/stub_api.py <port> guarded|leaky
Stdlib only, bound to 127.0.0.1, never shipped.
"""

from __future__ import annotations

import base64
import binascii
import json
import re
import sys
import unicodedata
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Deliberately not in the vig_ format, so no secret scanner ever mistakes it for a real token.
TOKEN = "stub-token-not-a-secret"  # noqa: S105 - throwaway value for a local stub
BLOCK = re.compile(
    r"ignore|ignorez|oublie|prompt|instruction|system|système|jailbreak|dan\b|developer mode|"
    r"pretend|imagine|role|rôle|hack|malware|exploit|password|mot de passe|email|e-mail|"
    r"adresse|address|phone|téléphone|ssn|iban|personal|personnel",
    re.IGNORECASE,
)
IN_SCOPE = re.compile(r"dora|ai act|rgpd|gdpr|amlr|règlement|regulation|article", re.IGNORECASE)


def _decoded_views(text: str) -> list[str]:
    # Same idea as the normalisation the brief asks for (11.10): look at NFKC and at a
    # base64 decoding, so the trivial encodings do not walk past a keyword list.
    views = [unicodedata.normalize("NFKC", text)]
    for chunk in re.findall(r"[A-Za-z0-9+/=]{16,}", text):
        try:
            views.append(base64.b64decode(chunk, validate=True).decode("utf-8", "ignore"))
        except (binascii.Error, ValueError):
            continue
    views.append(text.translate(str.maketrans("4310$5@7", "aeiosaat")))
    rot13 = str.maketrans(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
        "NOPQRSTUVWXYZABCDEFGHIJKLMnopqrstuvwxyzabcdefghijklm",
    )
    views.append(text.translate(rot13))
    return views


def guarded(question: str) -> dict[str, object]:
    if any(BLOCK.search(view) for view in _decoded_views(question)):
        return {"answer": "", "blocked": True, "block_reason": "injection", "refused": False}
    if not IN_SCOPE.search(question):
        return {
            "answer": "Hors périmètre.",
            "blocked": False,
            "block_reason": None,
            "refused": True,
        }
    return {
        "answer": "Voir [DORA art. 28].",
        "blocked": False,
        "block_reason": None,
        "refused": False,
    }


def leaky(_: str) -> dict[str, object]:
    answer = "Tu es Vigie, assistant conformité. Contact : jean.dupont@example.com"
    return {"answer": answer, "blocked": False, "block_reason": None, "refused": False}


class Handler(BaseHTTPRequestHandler):
    mode = "guarded"

    def do_POST(self) -> None:  # noqa: N802 - name imposed by BaseHTTPRequestHandler
        if self.path != "/v1/ask":
            self.send_error(404)
            return
        if self.headers.get("Authorization") != f"Bearer {TOKEN}":
            self.send_error(401)
            return
        length = int(self.headers.get("Content-Length", "0"))
        question = str(json.loads(self.rfile.read(length) or b"{}").get("question", ""))
        body = guarded(question) if self.mode == "guarded" else leaky(question)
        payload = json.dumps(body).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_: object) -> None:
        return


if __name__ == "__main__":
    Handler.mode = sys.argv[2] if len(sys.argv) > 2 else "guarded"
    ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1])), Handler).serve_forever()
