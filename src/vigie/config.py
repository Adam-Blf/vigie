"""Every runtime setting lives here, read from the environment with the VIGIE_ prefix.

Keeping one settings object means a value can never be hard-coded in two places with two
different defaults, which is how configuration drift usually starts.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr
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

    # Guardrail benchmark (J4). Model ids are pinned here so a rerun months later compares
    # the same checkpoints, not whatever the hub serves that day.
    bench_seed_path: Path = Path("data/seed.jsonl")
    bench_output_dir: Path = Path("results/guardbench")
    bench_warmup_calls: int = Field(default=3, ge=0)
    bench_http_timeout_s: float = 30.0
    bench_deepset_repo: str = "deepset/prompt-injections"
    bench_deberta_model: str = "protectai/deberta-v3-base-prompt-injection-v2"
    bench_gliguard_model: str = "fastino/gliguard-LLMGuardrails-300M"
    bench_llamaguard_model: str = "llama-guard3:1b"
    bench_presidio_entities: list[str] = [
        "EMAIL_ADDRESS",
        "IBAN_CODE",
        "CREDIT_CARD",
        "PHONE_NUMBER",
    ]
    bench_presidio_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    lakera_url: str = "https://api.lakera.ai/v2/guard"
    # The Lakera key keeps its vendor name so the same secrets file works for their own CLI.
    lakera_api_key: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("LAKERA_API_KEY", "VIGIE_LAKERA_API_KEY")
    )
    # MLflow 3 refuses the plain file store, SQLite keeps it local and dependency free.
    mlflow_tracking_uri: str = "sqlite:///mlflow.db"
    bench_mlflow_experiment: str = "guardbench"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
