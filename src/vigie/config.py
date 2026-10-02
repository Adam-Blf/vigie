"""Every runtime setting lives here, read from the environment with the VIGIE_ prefix.

Keeping one settings object means a value can never be hard-coded in two places with two
different defaults, which is how configuration drift usually starts.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

LLMProvider = Literal["ollama", "mistral", "fake"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VIGIE_", env_file=".env", extra="ignore")

    # Corpus and index
    data_dir: Path = Path("data")
    corpus_dir: Path = Path("data/corpus")
    qdrant_url: str | None = None
    qdrant_path: str | None = None
    qdrant_api_key: str | None = None
    collection: str = "vigie"
    dense_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    sparse_model: str = "Qdrant/bm25"
    top_k: int = Field(default=6, ge=1, le=20)

    # LLM
    llm_provider: LLMProvider = "ollama"
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "ministral-3:3b-instruct-2512-q4_K_M"
    llm_num_ctx: int = 4096
    llm_num_predict: int = 400
    llm_temperature: float = 0.1
    llm_timeout_s: float = 120.0
    mistral_api_key: str | None = None
    mistral_model: str = "ministral-3b-latest"
    mistral_url: str = "https://api.mistral.ai"
    # The fake LLM flag keeps its historical unprefixed name so the load and red teaming
    # scripts can flip it without knowing about the VIGIE_ convention.
    fake_llm_hallucinate: bool = Field(
        default=False,
        validation_alias=AliasChoices("FAKE_LLM_HALLUCINATE", "VIGIE_FAKE_LLM_HALLUCINATE"),
    )

    # RAG
    # Passages scoring below this are treated as noise, which is what lets an off-topic
    # question end in a refusal instead of an answer stitched from weak matches.
    rag_min_score: float = Field(default=0.0, ge=0.0)
    # An answer whose citations were all invented is not grounded, so it becomes a refusal.
    rag_require_citation: bool = True

    # API
    host: str = "127.0.0.1"
    port: int = 8710
    cors_origins: list[str] = ["http://127.0.0.1:4710", "http://localhost:4710"]
    db_path: Path = Path("data/vigie.sqlite3")
    audit_dir: Path = Path("data/audit")
    audit_retention_days: int = 30
    rate_limit_per_minute: int = 20
    daily_quota: int = 200
    max_question_chars: int = 2000
    maintenance: bool = False
    app_version: str = "0.1.0"
    bundle_version: str = "dev"
    fault_error_rate: float = Field(default=0.0, ge=0.0, le=1.0)

    # Guardrails
    guard_input_threshold: float = 0.5
    guard_enabled: bool = True


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
