"""Default provider: Ministral 3 3B served by a local Ollama through /api/chat.

On two Arm cores a full answer takes tens of seconds, so the client always streams and
the timeout is long. The model tag comes from the settings and is never guessed here.
"""

from __future__ import annotations

import json
from collections.abc import Generator, Sequence
from typing import Any

import httpx

from vigie.config import Settings
from vigie.llm.base import ChatMessage, LLMClient, LLMError, Usage


class OllamaClient(LLMClient):
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        num_ctx: int,
        num_predict: int,
        temperature: float,
        timeout_s: float,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.model = model
        self._options = {
            "num_ctx": num_ctx,
            "num_predict": num_predict,
            "temperature": temperature,
        }
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"), timeout=timeout_s, transport=transport
        )

    @classmethod
    def from_settings(
        cls, settings: Settings, transport: httpx.BaseTransport | None = None
    ) -> OllamaClient:
        return cls(
            base_url=settings.ollama_url,
            model=settings.ollama_model,
            num_ctx=settings.llm_num_ctx,
            num_predict=settings.llm_num_predict,
            temperature=settings.llm_temperature,
            timeout_s=settings.llm_timeout_s,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()
        super().close()

    def _payload(self, messages: Sequence[ChatMessage]) -> dict[str, Any]:
        return {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": True,
            "options": self._options,
        }

    def _deltas(self, messages: Sequence[ChatMessage]) -> Generator[str, None, Usage]:
        try:
            with self._client.stream("POST", "/api/chat", json=self._payload(messages)) as resp:
                if resp.status_code == httpx.codes.SERVICE_UNAVAILABLE:
                    # Ollama answers 503 when its bounded queue is full; the API turns
                    # this into a 503 with Retry-After instead of piling up requests.
                    raise LLMError("overloaded", "ollama queue is full")
                if resp.status_code != httpx.codes.OK:
                    resp.read()
                    raise LLMError("http", f"ollama returned HTTP {resp.status_code}")
                usage = Usage(0, 0)
                for line in resp.iter_lines():
                    if not line.strip():
                        continue
                    chunk = json.loads(line)
                    if "error" in chunk:
                        raise LLMError("model", str(chunk["error"]))
                    yield chunk.get("message", {}).get("content", "")
                    if chunk.get("done"):
                        usage = Usage(
                            int(chunk.get("prompt_eval_count", 0)),
                            int(chunk.get("eval_count", 0)),
                        )
                return usage
        except json.JSONDecodeError as exc:
            raise LLMError("http", "ollama sent a malformed stream line") from exc
        except httpx.TimeoutException as exc:
            raise LLMError("timeout", "ollama did not answer in time") from exc
        except httpx.TransportError as exc:
            raise LLMError("unavailable", "ollama is unreachable") from exc
