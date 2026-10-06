"""Lakera Guard, the only SaaS in the benchmark.

It is measured for comparison, not as a production candidate: sending a bank's
questions to a third-party API is a data transfer the compliance team would have to
sign off first, and its latency includes the round trip to their servers.
"""

from __future__ import annotations

from typing import Any

import httpx
from pydantic import SecretStr

from guardbench.guards.base import Guard, GuardUnavailableError, Verdict


def parse_response(payload: dict[str, Any]) -> Verdict:
    flagged = bool(payload.get("flagged", False))
    detectors = [
        str(item.get("detector_type", ""))
        for item in payload.get("breakdown", []) or []
        if item.get("detected")
    ]
    return Verdict(
        flagged=flagged,
        labels=tuple(sorted(d for d in detectors if d)),
        score=1.0 if flagged else 0.0,
    )


class LakeraGuard(Guard):
    name = "lakera"
    covers = frozenset(
        {
            "direct_injection",
            "indirect_injection",
            "jailbreak",
            "system_prompt_leak",
            "pii",
            "unsafe_content",
        }
    )

    def __init__(self, url: str, api_key: SecretStr | None, client: httpx.Client) -> None:
        self.url = url
        self.api_key = api_key
        self.client = client

    def setup(self) -> None:
        if self.api_key is None or not self.api_key.get_secret_value():
            raise GuardUnavailableError("LAKERA_API_KEY is not set, Lakera not tested")

    def check(self, text: str) -> Verdict:
        if self.api_key is None:
            raise GuardUnavailableError("LAKERA_API_KEY is not set")
        response = self.client.post(
            self.url,
            headers={"Authorization": f"Bearer {self.api_key.get_secret_value()}"},
            json={"messages": [{"role": "user", "content": text}], "breakdown": True},
        )
        response.raise_for_status()
        return parse_response(response.json())
