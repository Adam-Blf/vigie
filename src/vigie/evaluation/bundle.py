"""The configuration of a run as MLflow parameters, and the release bundle derived from it.

The bundle is what production reads (brief, section 11.8): a ConfigMap written from the
registered version, never a call to MLflow from the API. Everything that changes what a
user gets back goes in it, and nothing else, so two versions with the same bundle answer
the same way.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from vigie.config import Settings
from vigie.corpus.models import Chunk
from vigie.evaluation.golden import read_seal
from vigie.rag.prompt import PROMPT_VERSION
from vigie.retrieval.index import corpus_sha256

BUNDLE_SCHEMA = 1


def run_config(
    settings: Settings,
    *,
    embedding_id: str,
    collection: str,
    chunks: Sequence[Chunk],
    llm: str,
    depth: int,
) -> dict[str, str]:
    """Flat string parameters, the form MLflow stores and compares best."""
    seal = settings.golden_seal_path
    return {
        "embedding_model": settings.dense_model,
        "embedding_id": embedding_id,
        "sparse_model": settings.sparse_model,
        "sparse_language": settings.sparse_language,
        "fusion": "rrf",
        "rrf_k": str(settings.retrieval_rrf_k),
        "prefetch_limit": str(settings.retrieval_prefetch_limit),
        "rerank_model": settings.rerank_model or "none",
        "rerank_depth": str(settings.rerank_depth) if settings.rerank_model else "0",
        "pin_references": str(settings.retrieval_pin_references).lower(),
        "top_k": str(settings.top_k),
        "eval_depth": str(depth),
        "chunk_split_words": str(settings.corpus_split_words),
        "chunks": str(len(chunks)),
        "corpus_sha256": corpus_sha256(chunks),
        "collection": collection,
        "prompt_version": PROMPT_VERSION,
        "llm": llm,
        "ollama_model": settings.ollama_model,
        "golden_test_seal": read_seal(seal) if seal.exists() else "none",
    }


def build_bundle(report: Mapping[str, Any], settings: Settings, version: str) -> dict[str, Any]:
    """The release bundle of an evaluated configuration.

    Fault injection is always written as 0: a registered version is a candidate for
    production, the canary demonstration sets its own error rate on a copy.
    """
    config: Mapping[str, str] = report["config"]
    return {
        "schema": BUNDLE_SCHEMA,
        "version": version,
        "embedding": {
            "dense_model": config["embedding_model"],
            "sparse_model": config["sparse_model"],
            "sparse_language": config["sparse_language"],
            "fingerprint": config["embedding_id"],
        },
        "retrieval": {
            "fusion": config["fusion"],
            "rrf_k": int(config["rrf_k"]),
            "prefetch_limit": int(config["prefetch_limit"]),
            "rerank_model": "" if config["rerank_model"] == "none" else config["rerank_model"],
            "rerank_depth": int(config["rerank_depth"]),
            "pin_references": config["pin_references"] == "true",
            "top_k": int(config["top_k"]),
        },
        "prompt_version": config["prompt_version"],
        "llm": {"provider": "ollama", "model": config["ollama_model"]},
        "guard": {
            "enabled": settings.guard_enabled,
            "input_threshold": settings.guard_input_threshold,
        },
        "corpus_sha256": config["corpus_sha256"],
        "qdrant_collection": config["collection"],
        "fault_injection": {"error_rate": 0.0},
        "evaluation": {
            "split": report["split"],
            "metrics": report["metrics"],
            "ci": report["ci"],
        },
    }
