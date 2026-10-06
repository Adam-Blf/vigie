"""Builders and fakes shared by the quantization tests. No model, no network."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

import httpx
import numpy as np

from vigie.corpus.models import Chunk
from vigie.evaluation.golden import GoldenQuestion
from vigie.quant.dense import FloatArray, l2_normalize

VOCABULARY = ("tic", "direction", "donnees", "sanction", "prestataire", "risque")


def chunk(regulation: str, article: str, text: str, paragraph: str | None = None) -> Chunk:
    return Chunk(
        regulation=regulation,
        celex="32022R2554",
        kind="article",
        article=article,
        paragraph=paragraph,
        title="",
        chapter="I",
        text=text,
        url=f"https://example.test/{regulation}/{article}",
        eid=f"art_{article}",
        retrieved_on="2026-10-06",
    )


def question(
    qid: str,
    text: str,
    expected: Sequence[str] = ("DORA:5",),
    *,
    split: str = "dev",
    category: str = "in_scope",
) -> GoldenQuestion:
    return GoldenQuestion.model_validate(
        {
            "id": qid,
            "question": text,
            "lang": "fr",
            "expected_articles": list(expected),
            "reference_answer": "réponse",
            "category": category,
            "status": "verified",
            "authored_by": "Emilien Morice",
            "split": split,
        }
    )


class KeywordEncoder:
    """Bag of words over a tiny vocabulary: similar texts get similar vectors."""

    def __init__(self) -> None:
        self.calls = 0

    def encode(self, texts: Sequence[str]) -> FloatArray:
        self.calls += 1
        rows = [[t.lower().count(w) + 0.01 for w in VOCABULARY] for t in texts]
        return l2_normalize(np.asarray(rows, dtype=np.float32))


class StepClock:
    """Each call advances by ``step`` seconds, so every timed call lasts exactly that."""

    def __init__(self, step: float = 0.01) -> None:
        self.now = 0.0
        self.step = step

    def __call__(self) -> float:
        self.now += self.step
        return self.now


CHUNKS = [
    chunk("DORA", "5", "organe de direction et risque tic"),
    chunk("DORA", "5", "direction responsable tic", paragraph="2"),
    chunk("DORA", "28", "prestataire tiers de services tic prestataire"),
    chunk("RGPD", "83", "sanction administrative et donnees"),
]


ANSWER = "Les entités gèrent ce risque [DORA art. 28 §1]. Voir aussi [DORA art. 99]."


def stream_body(text: str, eval_count: int = 20, eval_ns: int = 2_000_000_000) -> bytes:
    lines = [{"message": {"content": ""}, "done": False}]
    lines += [{"message": {"content": word + " "}, "done": False} for word in text.split()]
    lines.append(
        {
            "message": {"content": ""},
            "done": True,
            "eval_count": eval_count,
            "eval_duration": eval_ns,
        }
    )
    return ("\n".join(json.dumps(line) for line in lines) + "\n\n").encode()


class FakeOllama:
    def __init__(self, text: str = ANSWER) -> None:
        self.text = text
        self.requests: list[tuple[str, Mapping[str, Any]]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else {}
        self.requests.append((request.url.path, body))
        if request.url.path == "/api/chat":
            return httpx.Response(200, content=stream_body(self.text))
        if request.url.path == "/api/ps":
            models = [{"name": "other", "size": 1}, {"model": "m:q4", "size": 3_000_000_000}]
            return httpx.Response(200, json={"models": models})
        return httpx.Response(200, json={"done": True})
