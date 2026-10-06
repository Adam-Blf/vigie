"""LLM part of J12: the same Ministral 3B in Q4_K_M and Q8_0, through the local Ollama.

Time to first token is measured on the client, from the request to the first non-empty
delta, because that is the wait a user feels. Decoding speed comes from Ollama's own
counters (``eval_count`` over ``eval_duration``), which exclude prompt processing. Memory
is what ``/api/ps`` reports for the loaded model.

Generation runs on the CPU only (``num_gpu: 0``): the target VM has no GPU, and a figure
helped by a laptop GPU would say nothing about it.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import httpx

from vigie.evaluation.golden import GoldenQuestion
from vigie.llm.base import ChatMessage
from vigie.quant.stats import summarize_latency
from vigie.rag.citations import validate_citations
from vigie.rag.labels import article_id
from vigie.rag.prompt import REFUSAL
from vigie.rag.types import Passage


@dataclass(frozen=True)
class Generation:
    text: str
    first_token_ms: float
    total_ms: float
    tokens_out: int
    eval_duration_ns: int


class OllamaProbe:
    def __init__(
        self,
        base_url: str,
        options: dict[str, float | int],
        timeout_s: float,
        transport: httpx.BaseTransport | None = None,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"), timeout=timeout_s, transport=transport
        )
        self._options = {**options, "num_gpu": 0}
        self._clock = clock

    def close(self) -> None:
        self._client.close()

    def chat(self, model: str, messages: Sequence[ChatMessage]) -> Generation:
        payload = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": True,
            "options": self._options,
        }
        start = self._clock()
        first: float | None = None
        parts: list[str] = []
        final: dict[str, object] = {}
        with self._client.stream("POST", "/api/chat", json=payload) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line.strip():
                    continue
                chunk = json.loads(line)
                if "error" in chunk:
                    raise RuntimeError(f"ollama error: {chunk['error']}")
                delta = chunk.get("message", {}).get("content", "")
                if delta and first is None:
                    first = self._clock()
                parts.append(delta)
                if chunk.get("done"):
                    final = chunk
        end = self._clock()
        if first is None:
            first = end
        return Generation(
            text="".join(parts),
            first_token_ms=(first - start) * 1000.0,
            total_ms=(end - start) * 1000.0,
            tokens_out=int(str(final.get("eval_count", 0))),
            eval_duration_ns=int(str(final.get("eval_duration", 0))),
        )

    def memory_bytes(self, model: str) -> int:
        """Resident size of ``model`` as reported by /api/ps, 0 if it is not loaded."""
        resp = self._client.get("/api/ps")
        resp.raise_for_status()
        for entry in resp.json().get("models", []):
            if entry.get("name") == model or entry.get("model") == model:
                return int(entry.get("size", 0))
        return 0

    def unload(self, model: str) -> None:
        resp = self._client.post("/api/generate", json={"model": model, "keep_alive": 0})
        resp.raise_for_status()


def select_questions(questions: Sequence[GoldenQuestion], count: int) -> list[GoldenQuestion]:
    """A fixed, spread out subset of the dev in-scope questions.

    Sorted by id then taken at even steps, so the four regulations are all represented and
    the subset never changes between two runs.
    """
    pool = sorted(
        (q for q in questions if q.split == "dev" and q.category == "in_scope"),
        key=lambda q: q.id,
    )
    if count > len(pool):
        raise ValueError(f"only {len(pool)} dev in-scope questions, {count} requested")
    return [pool[(i * len(pool)) // count] for i in range(count)]


@dataclass(frozen=True)
class AnswerQuality:
    raw_total: int
    raw_valid: int
    expected_cited: int
    expected_total: int
    refused: bool


def score_answer(text: str, passages: Sequence[Passage], expected: Sequence[str]) -> AnswerQuality:
    report = validate_citations(text, passages)
    cited = {article_id(c.regulation, c.article) for c in report.citations}
    return AnswerQuality(
        raw_total=report.raw_total,
        raw_valid=report.raw_valid,
        expected_cited=len(cited & set(expected)),
        expected_total=len(set(expected)),
        refused=REFUSAL.rstrip(".").casefold() in text.casefold(),
    )


@dataclass(frozen=True)
class LlmVariantResult:
    model: str
    questions: int
    first_token_p50_ms: float
    first_token_p95_ms: float
    tokens_per_s: float
    memory_bytes: int
    raw_citation_validity: float
    expected_coverage: float
    refusals: int


def summarize_llm(
    model: str,
    generations: Sequence[Generation],
    qualities: Sequence[AnswerQuality],
    memory_bytes: int,
) -> LlmVariantResult:
    if not generations or len(generations) != len(qualities):
        raise ValueError("one quality score per generation is required")
    first = summarize_latency([g.first_token_ms for g in generations], warmup=0)
    seconds = sum(g.eval_duration_ns for g in generations) / 1e9
    tokens = sum(g.tokens_out for g in generations)
    raw_total = sum(q.raw_total for q in qualities)
    expected = sum(q.expected_total for q in qualities)
    return LlmVariantResult(
        model=model,
        questions=len(generations),
        first_token_p50_ms=first.p50_ms,
        first_token_p95_ms=first.p95_ms,
        tokens_per_s=round(tokens / seconds, 2) if seconds else 0.0,
        memory_bytes=memory_bytes,
        raw_citation_validity=sum(q.raw_valid for q in qualities) / raw_total if raw_total else 1.0,
        expected_coverage=sum(q.expected_cited for q in qualities) / expected if expected else 0.0,
        refusals=sum(q.refused for q in qualities),
    )
