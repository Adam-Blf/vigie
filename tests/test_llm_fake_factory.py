from collections.abc import Generator, Sequence

import pytest

from rag_fixtures import passage
from vigie.config import Settings
from vigie.llm.base import ChatMessage, LLMClient, LLMError, Usage
from vigie.llm.factory import build_llm
from vigie.llm.fake import INVENTED_LABEL, FakeLLM
from vigie.llm.ollama import OllamaClient
from vigie.rag.prompt import REFUSAL, build_messages


def test_fake_answers_with_the_labels_of_the_passages() -> None:
    messages = build_messages("Quelles obligations ?", [passage("28", "1"), passage("30", "2")])
    result = FakeLLM().generate(messages)
    assert "[DORA art. 28 §1]" in result.text
    assert "[DORA art. 30 §2]" in result.text
    assert INVENTED_LABEL not in result.text
    assert result.tokens_out == len(result.text.split(" "))
    assert result.tokens_in > 0


def test_fake_is_deterministic() -> None:
    messages = build_messages("Q ?", [passage()])
    assert FakeLLM().generate(messages).text == FakeLLM().generate(messages).text


def test_fake_hallucinates_on_demand() -> None:
    result = FakeLLM(hallucinate=True).generate(build_messages("Q ?", [passage()]))
    assert INVENTED_LABEL in result.text


def test_fake_refuses_without_passages() -> None:
    assert FakeLLM().generate([ChatMessage("user", "Q ?")]).text == REFUSAL


def test_fake_streams_word_by_word() -> None:
    stream = FakeLLM().stream(build_messages("Q ?", [passage()]))
    deltas = list(stream)
    assert len(deltas) > 3
    assert "".join(deltas) == stream.result.text


class _EmptyDeltas(LLMClient):
    model = "empty"

    def _deltas(self, messages: Sequence[ChatMessage]) -> Generator[str, None, Usage]:
        yield ""
        yield "a"
        return Usage(1, 1)


def test_stream_skips_empty_deltas_and_guards_early_reads() -> None:
    stream = _EmptyDeltas().stream([])
    with pytest.raises(RuntimeError):
        _ = stream.result
    assert list(stream) == ["a"]
    assert stream.result.text == "a"


def test_factory_follows_the_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    assert isinstance(build_llm(Settings(_env_file=None)), OllamaClient)

    monkeypatch.setenv("VIGIE_LLM_PROVIDER", "fake")
    monkeypatch.setenv("FAKE_LLM_HALLUCINATE", "1")
    llm = build_llm(Settings(_env_file=None))
    assert isinstance(llm, FakeLLM)
    assert INVENTED_LABEL in llm.generate(build_messages("Q ?", [passage()])).text


def test_factory_refuses_mistral_without_a_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIGIE_LLM_PROVIDER", "mistral")
    with pytest.raises(LLMError) as err:
        build_llm(Settings(_env_file=None))
    assert err.value.kind == "disabled"
