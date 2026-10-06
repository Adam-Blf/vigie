"""Llama Guard 3 1B served by the local Ollama.

The model answers "safe", or "unsafe" followed by hazard codes S1 to S14 on the next
line. It was built for harmful content, not for prompt injection, and its scope says so.
"""

from __future__ import annotations

import httpx

from guardbench.guards.base import Guard, GuardUnavailableError, Verdict


def parse_answer(content: str) -> Verdict:
    lines = [line.strip() for line in content.strip().splitlines() if line.strip()]
    if not lines or lines[0].lower() != "unsafe":
        return Verdict(flagged=False)
    codes = tuple(code.strip() for line in lines[1:] for code in line.split(",") if code.strip())
    return Verdict(flagged=True, labels=codes or ("unsafe",), score=1.0)


class LlamaGuard(Guard):
    name = "llamaguard"
    covers = frozenset({"jailbreak", "unsafe_content", "pii"})

    def __init__(self, base_url: str, model: str, client: httpx.Client) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.client = client

    def setup(self) -> None:
        try:
            tags = self.client.get(f"{self.base_url}/api/tags").json()
        except httpx.HTTPError as exc:
            raise GuardUnavailableError(f"Ollama unreachable at {self.base_url}") from exc
        names = {m.get("name", "") for m in tags.get("models", [])}
        if self.model not in names:
            raise GuardUnavailableError(f"model {self.model} not pulled in Ollama")

    def check(self, text: str) -> Verdict:
        response = self.client.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": text}],
                "stream": False,
                "options": {"temperature": 0},
            },
        )
        response.raise_for_status()
        return parse_answer(str(response.json()["message"]["content"]))
