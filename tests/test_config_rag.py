import pytest
from pydantic import ValidationError

from vigie.config import Settings


def test_rag_defaults() -> None:
    settings = Settings(_env_file=None)
    assert settings.fake_llm_hallucinate is False
    assert settings.rag_min_score == 0.0
    assert settings.rag_require_citation is True
    assert settings.mistral_url == "https://api.mistral.ai"
    assert settings.ollama_model == "ministral-3:3b-instruct-2512-q4_K_M"


@pytest.mark.parametrize("name", ["FAKE_LLM_HALLUCINATE", "VIGIE_FAKE_LLM_HALLUCINATE"])
def test_hallucination_flag_reads_both_names(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    monkeypatch.setenv(name, "1")
    assert Settings(_env_file=None).fake_llm_hallucinate is True


def test_negative_min_score_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIGIE_RAG_MIN_SCORE", "-1")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_prompt_version_is_not_a_setting() -> None:
    # The version is tied to the prompt wording in vigie.rag.prompt, its single source:
    # a setting could claim a version that the code does not actually send.
    assert "prompt_version" not in Settings.model_fields
