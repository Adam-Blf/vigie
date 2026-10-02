from collections.abc import Generator, Sequence
from itertools import count

import pytest

from rag_fixtures import StubRetriever, passage
from vigie.llm.base import ChatMessage, LLMClient, Usage
from vigie.llm.fake import INVENTED_LABEL, FakeLLM
from vigie.rag.pipeline import RagPipeline
from vigie.rag.prompt import REFUSAL


class ScriptedLLM(LLMClient):
    """Answers with a fixed text, to drive the pipeline into each branch."""

    model = "scripted"

    def __init__(self, text: str) -> None:
        self.text = text
        self.calls = 0

    def _deltas(self, messages: Sequence[ChatMessage]) -> Generator[str, None, Usage]:
        self.calls += 1
        yield self.text
        return Usage(10, 3)


def pipeline(llm: LLMClient, *passages_: object, **kwargs: object) -> RagPipeline:
    retriever = StubRetriever(list(passages_))  # type: ignore[arg-type]
    return RagPipeline(retriever, llm, top_k=6, **kwargs)  # type: ignore[arg-type]


def test_valid_citation_is_kept() -> None:
    answer = pipeline(FakeLLM(), passage()).answer("Que dit DORA ?")
    assert not answer.refused
    assert [c.label for c in answer.citations] == ["[DORA art. 28 §1]"]
    assert answer.sources == [passage()]
    assert answer.model == "fake-llm"
    assert answer.raw_valid_rate == 1.0
    assert answer.tokens_out > 0


def test_invented_citation_is_removed() -> None:
    answer = pipeline(FakeLLM(hallucinate=True), passage()).answer("Que dit DORA ?")
    assert INVENTED_LABEL not in answer.text
    assert answer.removed_citations == [INVENTED_LABEL]
    assert answer.raw_valid_rate == 0.5
    assert not answer.refused


def test_empty_context_gives_the_refusal_without_calling_the_model() -> None:
    llm = ScriptedLLM("ne doit pas servir")
    answer = pipeline(llm).answer("Quelle est la capitale du Pérou ?")
    assert answer.refused
    assert answer.text == REFUSAL
    assert answer.citations == []
    assert answer.sources == []
    assert llm.calls == 0


def test_low_scores_count_as_no_context() -> None:
    llm = ScriptedLLM("x")
    answer = pipeline(llm, passage(score=0.01), min_score=0.2).answer("Q ?")
    assert answer.refused
    assert llm.calls == 0


def test_model_refusal_is_reported_as_refused() -> None:
    answer = pipeline(ScriptedLLM(f"« {REFUSAL} »"), passage()).answer("Q ?")
    assert answer.refused
    assert answer.text == REFUSAL
    assert answer.sources == [passage()]


def test_answer_whose_citations_are_all_invented_becomes_a_refusal() -> None:
    answer = pipeline(ScriptedLLM("Règle [DORA art. 999 §9]."), passage()).answer("Q ?")
    assert answer.refused
    assert answer.removed_citations == ["[DORA art. 999 §9]"]


def test_uncited_answer_is_kept_when_citations_are_not_required() -> None:
    llm = ScriptedLLM("Réponse sans citation.")
    answer = pipeline(llm, passage(), require_citation=False).answer("Q ?")
    assert not answer.refused
    assert answer.text == "Réponse sans citation."


def test_streaming_yields_the_full_text() -> None:
    stream = pipeline(FakeLLM(), passage(), passage("30", "2")).stream("Q ?", trace_id="t-1")
    deltas = list(stream)
    assert len(deltas) > 1
    assert "".join(deltas) == stream.answer.text
    assert stream.answer.trace_id == "t-1"


def test_streamed_refusal_is_a_single_delta() -> None:
    stream = pipeline(FakeLLM()).stream("Q ?")
    assert list(stream) == [REFUSAL]
    assert stream.answer.refused


def test_answer_is_unavailable_before_the_stream_ends() -> None:
    stream = pipeline(FakeLLM(), passage()).stream("Q ?")
    with pytest.raises(RuntimeError):
        _ = stream.answer


def test_timings_and_trace_id() -> None:
    ticks = count()
    clock = lambda: next(ticks) / 10  # noqa: E731 - each call advances 100 ms
    answer = pipeline(ScriptedLLM("R [DORA art. 28 §1]."), passage(), clock=clock).answer("Q ?")
    timings = answer.timings
    assert timings.retrieval_ms == 100.0
    assert timings.first_token_ms == 200.0
    assert timings.generation_ms == 200.0
    assert timings.total_ms == 300.0
    assert len(answer.trace_id) == 32


def test_retriever_receives_question_and_top_k() -> None:
    retriever = StubRetriever([passage()])
    RagPipeline(retriever, FakeLLM(), top_k=4).answer("Q ?")
    assert retriever.calls == [("Q ?", 4)]
