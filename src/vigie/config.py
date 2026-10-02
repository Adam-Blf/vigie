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

    # Kubernetes budget of the single Always Free node (12 GB, 2 OCPU, brief 11.7).
    # 1.5 GB stays outside Kubernetes for the OS; k3s itself takes the reserve.
    k8s_requests_budget_mib: int = 8704
    k8s_limits_budget_mib: int = 10752
    k8s_system_reserve_mib: int = 1229
    k8s_cpu_requests_budget_m: int = 1800


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
