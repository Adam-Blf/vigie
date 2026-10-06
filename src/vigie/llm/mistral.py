"""Optional provider: the hosted Mistral API.

Since 2026 the free tier no longer issues API keys, so this stays off unless someone
decides to pay for a key. No milestone depends on it; it exists so that switching away
from the local model is a configuration change and not a code change.
"""

from __future__ import annotations

import json
from collections.abc import Generator, Sequence

import httpx

from vigie.config import Settings
from vigie.llm.base import ChatMessage, LLMClient, LLMError, Usage

_DATA_PREFIX = "data:"
_DONE = "[DONE]"


class MistralClient(LLMClient):
    def __init__(
        self,
        *,
        api_key: str | None,
        model: str,
        base_url: str,
        max_tokens: int,
        temperature: float,
        timeout_s: float,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not api_key:
            raise LLMError("disabled", "the Mistral provider needs VIGIE_MISTRAL_API_KEY")
        self.model = model
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout_s,
            transport=transport,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    @classmethod
    def from_settings(
        cls, settings: Settings, transport: httpx.BaseTransport | None = None
    ) -> MistralClient:
        return cls(
            api_key=settings.mistral_api_key,
            model=settings.mistral_model,
            base_url=settings.mistral_url,
            max_tokens=settings.llm_num_predict,
            temperature=settings.llm_temperature,
            timeout_s=settings.llm_timeout_s,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()
        super().close()

    def _deltas(self, messages: Sequence[ChatMessage]) -> Generator[str, None, Usage]:
        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": True,
            "max_tokens": self._max_tokens,
            "temperature": self._temperature,
        }
        try:
            with self._client.stream("POST", "/v1/chat/completions", json=payload) as resp:
                if resp.status_code == httpx.codes.TOO_MANY_REQUESTS:
                    raise LLMError("overloaded", "mistral rate limit reached")
                if resp.status_code != httpx.codes.OK:
                    resp.read()
                    raise LLMError("http", f"mistral returned HTTP {resp.status_code}")
                usage = Usage(0, 0)
                for line in resp.iter_lines():
                    if not line.startswith(_DATA_PREFIX):
                        continue
                    data = line[len(_DATA_PREFIX) :].strip()
                    if data == _DONE:
                        break
                    chunk = json.loads(data)
                    for choice in chunk.get("choices", []):
                        yield choice.get("delta", {}).get("content") or ""
                    if chunk.get("usage"):
                        usage = Usage(
                            int(chunk["usage"].get("prompt_tokens", 0)),
                            int(chunk["usage"].get("completion_tokens", 0)),
                        )
                return usage
        except json.JSONDecodeError as exc:
            raise LLMError("http", "mistral sent a malformed stream line") from exc
        except httpx.TimeoutException as exc:
            raise LLMError("timeout", "mistral did not answer in time") from exc
        except httpx.TransportError as exc:
            raise LLMError("unavailable", "mistral is unreachable") from exc
