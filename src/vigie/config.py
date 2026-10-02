"""Every runtime setting lives here, read from the environment with the VIGIE_ prefix.

Keeping one settings object means a value can never be hard-coded in two places with two
different defaults, which is how configuration drift usually starts.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
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

    # Corpus ingestion. Cellar is the only EUR-Lex door that answers robots, and only over
    # HTTPS here: its redirects point to plain HTTP, the fetcher upgrades them.
    cellar_base_url: str = "https://publications.europa.eu/resource/celex/"
    cellar_allowed_host: str = "publications.europa.eu"
    eurlex_base_url: str = "https://eur-lex.europa.eu/legal-content/FR/TXT/?uri=CELEX:"
    corpus_language: str = "fra"
    corpus_user_agent: str = "vigie-corpus/0.1 (EFREI MLOps course; adam.beloucif@efrei.net)"
    corpus_cache_dir: Path = Path("data/cache")
    corpus_lock_path: Path = Path("data/corpus.lock")
    corpus_min_interval_s: float = Field(default=1.0, ge=1.0)
    corpus_max_retries: int = Field(default=4, ge=0, le=10)
    corpus_backoff_s: float = Field(default=2.0, gt=0.0)
    corpus_timeout_s: float = 60.0
    corpus_max_redirects: int = 5
    corpus_split_words: int = Field(default=1200, ge=50)

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
    prompt_version: str = "v1"

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
