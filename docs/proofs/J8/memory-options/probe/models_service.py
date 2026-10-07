"""Throwaway vigie-models service for the shared-model estimate of docs/memory-options.md.

Holds the embedder (dense plus BM25) and the guard classifier the settings name, and
serves them over HTTP to API pods started with VIGIE_PROBE_REMOTE_MODELS. Same image as
the API, started with `python /probe/models_service.py`. A measurement stub: no auth, no
batching, one uvicorn worker, never meant for the cluster as written.
"""

from __future__ import annotations

import os
from typing import Any

import uvicorn
from fastapi import FastAPI

from vigie.config import get_settings
from vigie.guard.classifier import InjectionClassifier
from vigie.retrieval.embeddings import Embedded, FastEmbedEmbedder

settings = get_settings()
embedder = FastEmbedEmbedder.from_settings(settings)
classifier = InjectionClassifier.load(
    settings.guard_model_dir, settings.guard_max_tokens, settings.guard_threads
)
app = FastAPI()


def as_json(item: Embedded) -> dict[str, Any]:
    return {
        "dense": list(item.dense),
        "indices": list(item.sparse.indices),
        "values": list(item.sparse.values),
    }


@app.post("/info")
def info() -> dict[str, Any]:
    return {"embedding_id": embedder.embedding_id, "dense_size": embedder.dense_size}


@app.post("/embed_query")
def embed_query(body: dict[str, str]) -> dict[str, Any]:
    return as_json(embedder.embed_query(body["text"]))


@app.post("/embed_documents")
def embed_documents(body: dict[str, list[str]]) -> dict[str, Any]:
    return {"items": [as_json(e) for e in embedder.embed_documents(body["texts"])]}


@app.post("/guard_score")
def guard_score(body: dict[str, str]) -> dict[str, float]:
    return {"score": classifier.score(body["text"])}


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("MODELS_PORT", "8800")))  # noqa: S104
