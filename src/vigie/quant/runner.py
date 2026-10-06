"""Glue between the measurements and their outputs: JSON results, MLflow runs, the decision.

Everything heavy is passed in (encoders, the Ollama probe, the MLflow module), so the
orchestration itself runs in the unit tests with fakes and no network.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any

from vigie.corpus.models import Chunk
from vigie.evaluation.golden import GoldenQuestion
from vigie.quant.decision import Decision, QuantThreshold, VariantResult, compare
from vigie.quant.dense import chunk_text
from vigie.quant.llm_bench import (
    AnswerQuality,
    Generation,
    LlmVariantResult,
    OllamaProbe,
    score_answer,
    summarize_llm,
)
from vigie.quant.study import Encoder, StudySettings, measure_variant, top_passages
from vigie.rag.prompt import PROMPT_VERSION, build_messages
from vigie.rag.types import Passage

WARMUP_QUESTION = "Question de préchauffage, hors mesure : que couvrent ces extraits ?"

LogRun = Callable[[str, Mapping[str, str | int | float], Mapping[str, float]], str]


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    path.write_text(text + "\n", encoding="utf-8")


def run_embedding_study(
    variants: Mapping[str, tuple[Encoder, int]],
    chunks: Sequence[Chunk],
    questions: Sequence[GoldenQuestion],
    threshold: QuantThreshold,
    settings: StudySettings,
    log_run: LogRun | None = None,
) -> tuple[dict[str, VariantResult], Decision]:
    """Measure ``fp32`` and ``int8`` with the same questions and decide between them."""
    if set(variants) != {"fp32", "int8"}:
        raise ValueError("the study compares exactly the fp32 and int8 variants")
    results: dict[str, VariantResult] = {}
    for name in ("fp32", "int8"):
        encoder, size = variants[name]
        result = measure_variant(name, encoder, size, chunks, questions, settings)
        results[name] = result
        if log_run is not None:
            params = {
                "variant": name,
                "split": threshold.split,
                "k": threshold.k,
                "questions": result.questions,
                "chunks": len(chunks),
                "warmup": settings.warmup,
                "passes": settings.passes,
            }
            metrics = {
                "size_mb": result.size_bytes / 1e6,
                "recall_at_k": result.recall_at_k,
                "mrr": result.mrr,
                "latency_p50_ms": result.latency_p50_ms,
                "latency_p95_ms": result.latency_p95_ms,
            }
            log_run(f"embedding-{name}", params, metrics)
    return results, compare(results["fp32"], results["int8"], threshold)


def embedding_payload(
    results: Mapping[str, VariantResult], decision: Decision, threshold: QuantThreshold
) -> dict[str, Any]:
    return {
        "threshold": threshold.model_dump(),
        "variants": {name: asdict(result) for name, result in results.items()},
        "decision": {
            "keep_int8": decision.keep_int8,
            "deployed": decision.deployed,
            "recall_drop": decision.recall_drop,
            "size_ratio": decision.size_ratio,
            "reasons": list(decision.reasons),
        },
    }


def llm_items(
    encoder: Encoder,
    chunks: Sequence[Chunk],
    questions: Sequence[GoldenQuestion],
    top_k: int,
) -> list[tuple[GoldenQuestion, list[Passage]]]:
    """Retrieve the passages once, so both LLM variants answer from identical context."""
    documents = encoder.encode([chunk_text(c) for c in chunks])
    queries = encoder.encode([q.question for q in questions])
    return [
        (question, top_passages(queries[i], documents, chunks, top_k))
        for i, question in enumerate(questions)
    ]


def run_llm_variant(
    probe: OllamaProbe,
    model: str,
    items: Sequence[tuple[GoldenQuestion, list[Passage]]],
    log_run: LogRun | None = None,
    on_answer: Callable[[list[dict[str, Any]]], None] | None = None,
) -> tuple[LlmVariantResult, list[dict[str, Any]]]:
    """Warm the model up on the first item, then measure every item and free the memory.

    ``on_answer`` receives the answers so far after each one: a CPU run takes minutes per
    answer, and an incident near the end must not throw away what was already measured.
    """
    # The warm-up loads the weights. It must not share its full prompt with a measured
    # item, or Ollama's prompt cache would hand that item a near zero first token time.
    _, first_passages = items[0]
    probe.chat(model, build_messages(WARMUP_QUESTION, first_passages[::-1]))
    generations: list[Generation] = []
    qualities: list[AnswerQuality] = []
    answers: list[dict[str, Any]] = []
    for question, passages in items:
        generation = probe.chat(model, build_messages(question.question, passages))
        quality = score_answer(generation.text, passages, question.expected_articles)
        generations.append(generation)
        qualities.append(quality)
        answers.append({"id": question.id, **asdict(generation), **asdict(quality)})
        if on_answer is not None:
            on_answer(answers)
    memory = probe.memory_bytes(model)
    probe.unload(model)
    result = summarize_llm(model, generations, qualities, memory)
    if log_run is not None:
        metrics = {k: float(v) for k, v in asdict(result).items() if k != "model"}
        log_run(
            f"llm-{model}",
            {"model": model, "prompt_version": PROMPT_VERSION, "questions": len(items)},
            metrics,
        )
    return result, answers
