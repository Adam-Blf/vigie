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
DenseVariant = Literal["fp32", "int8"]


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

    # Red teaming: share of replayed attacks allowed to get through before CI fails (brief 11.3)
    redteam_max_attack_success_rate: float = Field(default=0.05, ge=0.0, le=1.0)

    # Load test (J11). The thresholds are written in eval/thresholds.yaml (section load);
    # these defaults must stay equal to it, which tests/loadtest enforces.
    load_token: SecretStr | None = None
    load_p95_ms: float = Field(default=500.0, gt=0)
    load_max_error_ratio: float = Field(default=0.01, ge=0.0, le=1.0)
    load_max_attack_leak_ratio: float = Field(default=0.10, ge=0.0, le=1.0)

    # Drift. The defaults were calibrated on the multilingual MiniLM model: in-scope
    # questions sit above 0.3 of similarity to the nearest corpus centroid, off-topic
    # ones around 0, so 0.3 leaves room on both sides.
    drift_reference_path: Path = Path("data/drift/reference.npy")
    drift_anchors_path: Path = Path("data/drift/anchors.npy")
    drift_window_size: int = Field(default=500, ge=10)
    drift_min_window: int = Field(default=30, ge=5)
    drift_evaluate_every: int = Field(default=10, ge=1)
    drift_centroid_threshold: float = Field(default=0.3, gt=0.0, le=2.0)
    drift_out_of_scope_similarity: float = Field(default=0.3, ge=-1.0, le=1.0)
    drift_out_of_scope_ratio: float = Field(default=0.25, gt=0.0, le=1.0)
    drift_ks_alpha: float = Field(default=0.01, gt=0.0, lt=1.0)

    # Guardrail benchmark (J4). Model ids are pinned here so a rerun months later compares
    # the same checkpoints, not whatever the hub serves that day.
    bench_seed_path: Path = Path("data/seed.jsonl")
    bench_output_dir: Path = Path("results/guardbench")
    bench_warmup_calls: int = Field(default=3, ge=0)
    bench_http_timeout_s: float = 30.0
    # Two threads, like the 2 OCPU Oracle VM; the default (every core) also made the
    # timings swing with whatever else ran on the laptop.
    bench_torch_threads: int = Field(default=2, ge=1)
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

    # Evaluation
    golden_path: Path = Path("data/golden/questions.jsonl")
    golden_seal_path: Path = Path("data/golden/test.sha256")
    thresholds_path: Path = Path("eval/thresholds.yaml")

    # Quantization (J12). The deployed embedding variant is the outcome of the study in
    # docs/quantization.md, applied here and nowhere else.
    dense_variant: DenseVariant = "fp32"
    # Pinned commit of the Hugging Face repository, so an upstream push cannot change the
    # weights the study measured.
    dense_model_revision: str = "e8f8c211226b894fcb81acc59f3b34ba3efd5f42"
    dense_max_tokens: int = Field(default=128, ge=8, le=512)
    quant_dir: Path = Path("data/quant")
    quant_warmup_queries: int = Field(default=5, ge=0)
    quant_latency_passes: int = Field(default=3, ge=1)
    quant_llm_questions: int = Field(default=10, ge=1)
    quant_llm_models: list[str] = [
        "ministral-3:3b-instruct-2512-q4_K_M",
        "ministral-3:3b-instruct-2512-q8_0",
    ]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
