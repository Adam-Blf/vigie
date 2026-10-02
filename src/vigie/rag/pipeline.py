"""Question in, cited answer out: retrieval, prompt, generation, citation check.

The retriever is a protocol so this layer can be built and tested before the Qdrant
index exists; any object with search(question, top_k) fits.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable, Generator, Iterator
from dataclasses import replace
from typing import Protocol

from vigie.llm.base import LLMClient
from vigie.rag.citations import validate_citations
from vigie.rag.prompt import REFUSAL, build_messages
from vigie.rag.types import Answer, Passage, Timings

_REFUSAL_KEY = REFUSAL.rstrip(".").casefold()


class Retriever(Protocol):
    def search(self, question: str, top_k: int) -> list[Passage]: ...


class AnswerStream:
    """Yields text deltas as they arrive, then holds the validated Answer.

    The deltas are the raw model output. The final Answer is the one to trust: invented
    citations are removed from it, so a streaming client must replace what it displayed
    with Answer.text once the stream ends.
    """

    def __init__(self, steps: Generator[str, None, Answer]) -> None:
        self._steps = steps
        self._answer: Answer | None = None

    def __iter__(self) -> Iterator[str]:
        while True:
            try:
                delta = next(self._steps)
            except StopIteration as stop:
                self._answer = stop.value
                return
            yield delta

    @property
    def answer(self) -> Answer:
        if self._answer is None:
            raise RuntimeError("the stream must be fully consumed before reading the answer")
        return self._answer


def _ms(start: float, end: float) -> float:
    return round((end - start) * 1000, 1)


class RagPipeline:
    def __init__(
        self,
        retriever: Retriever,
        llm: LLMClient,
        *,
        top_k: int,
        min_score: float = 0.0,
        require_citation: bool = True,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self._retriever = retriever
        self._llm = llm
        self._top_k = top_k
        self._min_score = min_score
        self._require_citation = require_citation
        self._clock = clock

    def stream(self, question: str, trace_id: str | None = None) -> AnswerStream:
        return AnswerStream(self._run(question, trace_id or uuid.uuid4().hex))

    def answer(self, question: str, trace_id: str | None = None) -> Answer:
        stream = self.stream(question, trace_id)
        for _ in stream:
            pass
        return stream.answer

    def _run(self, question: str, trace_id: str) -> Generator[str, None, Answer]:
        start = self._clock()
        found = self._retriever.search(question, self._top_k)
        passages = [p for p in found if p.score >= self._min_score]
        retrieved = self._clock()

        if not passages:
            # Nothing relevant: refuse without spending a slow generation on it.
            yield REFUSAL
            timings = Timings(_ms(start, retrieved), None, 0.0, _ms(start, self._clock()))
            return Answer(REFUSAL, [], [], True, trace_id, timings, model=self._llm.model)

        llm_stream = self._llm.stream(build_messages(question, passages))
        first_token: float | None = None
        for delta in llm_stream:
            if first_token is None:
                first_token = self._clock()
            yield delta
        result = llm_stream.result
        end = self._clock()

        timings = Timings(
            retrieval_ms=_ms(start, retrieved),
            first_token_ms=_ms(start, first_token) if first_token is not None else None,
            generation_ms=_ms(retrieved, end),
            total_ms=_ms(start, end),
        )
        report = validate_citations(result.text, passages)
        answer = Answer(
            text=report.text,
            citations=report.citations,
            sources=passages,
            refused=False,
            trace_id=trace_id,
            timings=timings,
            model=self._llm.model,
            tokens_in=result.tokens_in,
            tokens_out=result.tokens_out,
            removed_citations=report.removed,
            raw_valid_rate=report.raw_valid_rate,
        )
        said_no = _REFUSAL_KEY in result.text.casefold()
        # With every citation filtered out, nothing backs the text any more.
        unsupported = self._require_citation and not report.citations
        if said_no or unsupported:
            return replace(answer, text=REFUSAL, citations=[], refused=True)
        return answer
