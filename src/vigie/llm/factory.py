"""Builds the configured LLM client.

The provider comes from the settings only. Nothing here accepts a value from a request:
letting a caller pick the provider through a header would let anyone switch production
to the fake model, or to a paid API, with one line of curl.
"""

from __future__ import annotations

from vigie.config import Settings
from vigie.llm.base import LLMClient
from vigie.llm.fake import FakeLLM
from vigie.llm.mistral import MistralClient
from vigie.llm.ollama import OllamaClient


def build_llm(settings: Settings) -> LLMClient:
    if settings.llm_provider == "fake":
        return FakeLLM(hallucinate=settings.fake_llm_hallucinate)
    if settings.llm_provider == "mistral":
        return MistralClient.from_settings(settings)
    return OllamaClient.from_settings(settings)
