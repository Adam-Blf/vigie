import pytest
from pydantic import ValidationError
from pydantic_settings import SettingsConfigDict

from vigie.config import Settings, get_settings


class IsolatedSettings(Settings):
    """Settings that read the environment only, never a local .env file."""

    model_config = SettingsConfigDict({**Settings.model_config, "env_file": None})


def test_defaults_bind_locally_and_use_local_llm() -> None:
    settings = IsolatedSettings()
    assert settings.host == "127.0.0.1"
    assert settings.llm_provider == "ollama"
    assert settings.fault_error_rate == 0.0


def test_environment_overrides_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIGIE_LLM_PROVIDER", "fake")
    monkeypatch.setenv("VIGIE_TOP_K", "3")
    settings = IsolatedSettings()
    assert settings.llm_provider == "fake"
    assert settings.top_k == 3


def test_unknown_provider_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIGIE_LLM_PROVIDER", "openai")
    with pytest.raises(ValidationError):
        IsolatedSettings()


def test_get_settings_is_cached() -> None:
    get_settings.cache_clear()
    assert get_settings() is get_settings()


def test_corpus_defaults_stay_polite_and_on_https() -> None:
    settings = Settings(_env_file=None)
    assert settings.cellar_base_url.startswith("https://publications.europa.eu/")
    assert settings.eurlex_base_url.startswith("https://eur-lex.europa.eu/")
    assert settings.corpus_min_interval_s == 1.0
    assert settings.corpus_split_words == 1200
    assert "vigie" in settings.corpus_user_agent


def test_corpus_rate_limit_cannot_go_below_one_request_per_second(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIGIE_CORPUS_MIN_INTERVAL_S", "0.2")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)
