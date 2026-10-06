import httpx
import pytest

from quant_fixtures import ANSWER, FakeOllama, StepClock, question
from rag_fixtures import passage
from vigie.llm.base import ChatMessage
from vigie.quant.llm_bench import (
    AnswerQuality,
    Generation,
    OllamaProbe,
    score_answer,
    select_questions,
    summarize_llm,
)
from vigie.quant.runner import run_llm_variant
from vigie.rag.prompt import REFUSAL


def probe(fake: FakeOllama, step: float = 0.1) -> OllamaProbe:
    return OllamaProbe(
        "http://ollama.test/",
        {"temperature": 0.1},
        30.0,
        transport=httpx.MockTransport(fake),
        clock=StepClock(step),
    )


def test_chat_measures_first_token_on_the_client_and_forces_the_cpu() -> None:
    fake = FakeOllama("un deux")
    generation = probe(fake).chat("m:q4", [ChatMessage("user", "q")])
    assert generation.text == "un deux "
    # Clock ticks: start, first non-empty delta, end. The empty first delta is not a token.
    assert generation.first_token_ms == pytest.approx(100.0)
    assert generation.total_ms == pytest.approx(200.0)
    assert generation.tokens_out == 20
    assert fake.requests[0][1]["options"] == {"temperature": 0.1, "num_gpu": 0}


def test_chat_without_any_token_reports_the_full_wait() -> None:
    generation = probe(FakeOllama("")).chat("m:q4", [ChatMessage("user", "q")])
    assert generation.first_token_ms == generation.total_ms


def test_chat_raises_on_an_error_line() -> None:
    transport = httpx.MockTransport(lambda r: httpx.Response(200, content=b'{"error": "boom"}\n'))
    client = OllamaProbe("http://ollama.test", {}, 5.0, transport=transport)
    with pytest.raises(RuntimeError, match="boom"):
        client.chat("m", [ChatMessage("user", "q")])


def test_memory_is_read_from_api_ps_and_zero_when_not_loaded() -> None:
    client = probe(FakeOllama())
    assert client.memory_bytes("m:q4") == 3_000_000_000
    assert client.memory_bytes("absent") == 0


def test_select_questions_is_fixed_and_spread_over_the_dev_in_scope_rows() -> None:
    rows = [question(f"q{i:02d}", "x") for i in range(20)]
    rows += [question("t", "x", split="test"), question("o", "x", category="trap")]
    picked = select_questions(rows, 4)
    assert [q.id for q in picked] == ["q00", "q05", "q10", "q15"]
    with pytest.raises(ValueError, match="only 20"):
        select_questions(rows, 21)


def test_score_answer_counts_raw_validity_and_expected_coverage() -> None:
    quality = score_answer(ANSWER, [passage("28", "1")], ["DORA:28", "DORA:30"])
    assert quality == AnswerQuality(2, 1, 1, 2, refused=False)
    assert score_answer(REFUSAL, [passage()], ["DORA:28"]).refused


def test_summarize_llm_aggregates_speed_memory_and_quality() -> None:
    generations = [Generation("a", 1000.0, 5000.0, 30, 3_000_000_000)] * 2
    qualities = [AnswerQuality(2, 1, 1, 1, False), AnswerQuality(0, 0, 0, 1, True)]
    result = summarize_llm("m", generations, qualities, 42)
    assert result.tokens_per_s == 10.0
    assert result.raw_citation_validity == 0.5
    assert result.expected_coverage == 0.5
    assert result.refusals == 1
    assert result.first_token_p95_ms == 1000.0


def test_summarize_llm_edge_cases() -> None:
    silent = summarize_llm(
        "m", [Generation("", 1.0, 1.0, 0, 0)], [AnswerQuality(0, 0, 0, 0, True)], 0
    )
    assert (silent.tokens_per_s, silent.raw_citation_validity, silent.expected_coverage) == (
        0.0,
        1.0,
        0.0,
    )
    with pytest.raises(ValueError):
        summarize_llm("m", [], [], 0)


def test_run_llm_variant_warms_up_measures_then_unloads() -> None:
    fake = FakeOllama()
    items = [(question("dora-1", "q", ("DORA:28",)), [passage("28", "1")])] * 3
    logged: list[str] = []
    result, answers = run_llm_variant(
        probe(fake), "m:q4", items, lambda name, params, metrics: logged.append(name) or name
    )
    paths = [path for path, _ in fake.requests]
    assert paths == ["/api/chat"] * 4 + ["/api/ps", "/api/generate"]
    assert fake.requests[-1][1] == {"model": "m:q4", "keep_alive": 0}
    assert result.questions == 3
    assert result.memory_bytes == 3_000_000_000
    assert result.expected_coverage == 1.0
    assert answers[0]["id"] == "dora-1"
    assert answers[0]["raw_valid"] == 1
    assert logged == ["llm-m:q4"]
