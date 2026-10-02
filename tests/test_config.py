import pytest
from pydantic import ValidationError

from vigie.config import Settings, get_settings


def test_defaults_bind_locally_and_use_local_llm() -> None:
    settings = Settings(_env_file=None)
    assert settings.host == "127.0.0.1"
    assert settings.llm_provider == "ollama"
    assert settings.fault_error_rate == 0.0


def test_environment_overrides_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIGIE_LLM_PROVIDER", "fake")
    monkeypatch.setenv("VIGIE_TOP_K", "3")
    settings = Settings(_env_file=None)
    assert settings.llm_provider == "fake"
    assert settings.top_k == 3


def test_unknown_provider_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIGIE_LLM_PROVIDER", "openai")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_get_settings_is_cached() -> None:
    get_settings.cache_clear()
    assert get_settings() is get_settings()


def test_infra_state_stays_out_of_the_repository() -> None:
    settings = Settings(_env_file=None)
    assert settings.infra_state_dir.is_absolute()
    assert settings.infra_state_dir.parts[-2:] == (".vigie", "terraform")
    assert settings.infra_retry_interval_s == 600
    assert settings.infra_retry_max_attempts == 1008


def test_infra_retry_interval_has_a_floor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIGIE_INFRA_RETRY_INTERVAL_S", "5")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)
