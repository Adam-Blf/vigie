"""Every runtime setting lives here, read from the environment with the VIGIE_ prefix.

Keeping one settings object means a value can never be hard-coded in two places with two
different defaults, which is how configuration drift usually starts.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from socket import gethostname
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from vigie import __version__

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
    # Tokens and usage share one SQLite file in WAL mode, on a single volume.
    db_path: Path = Path("data/vigie.sqlite3")
    token_ttl_days: int = Field(default=30, ge=1, le=365)
    audit_dir: Path = Path("data/audit")
    audit_retention_days: int = Field(default=30, ge=1)
    # One audit file per pod: two replicas appending to one chained file would fork it.
    audit_pod_name: str = Field(default_factory=gethostname)
    rate_limit_per_minute: int = Field(default=20, ge=1)
    daily_quota: int = Field(default=200, ge=1)
    max_question_chars: int = Field(default=2000, ge=1)
    max_body_bytes: int = Field(default=16384, ge=1024)
    # Kill switch from the incident runbook: every /v1 route answers 503 while it is on.
    maintenance: bool = False
    app_version: str = __version__
    bundle_version: str = "dev"
    bundle_path: Path | None = None
    fault_error_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    # Generations running at once in this pod. Past it the API answers 503 with
    # Retry-After at once, instead of queueing work the two VM cores cannot absorb.
    llm_max_inflight: int = Field(default=2, ge=1)
    retry_after_s: int = Field(default=10, ge=1)
    # The local model costs nothing per token. A reference price lets the usage page
    # show what the same traffic would cost on a hosted API.
    usage_cost_per_1k_tokens_eur: float = Field(default=0.0, ge=0.0)
    # Passages served by the static retriever until the Qdrant retriever is wired in.
    static_passages_path: Path | None = None
    readiness_timeout_s: float = Field(default=2.0, gt=0.0)

    # Guardrails
    guard_input_threshold: float = 0.5
    guard_enabled: bool = True

    # Evaluation
    golden_path: Path = Path("data/golden/questions.jsonl")
    golden_seal_path: Path = Path("data/golden/test.sha256")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
