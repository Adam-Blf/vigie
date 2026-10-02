import pytest

from vigie.config import Settings


def test_benchmark_defaults_pin_models_and_stay_local(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LAKERA_API_KEY", raising=False)
    monkeypatch.delenv("VIGIE_LAKERA_API_KEY", raising=False)
    settings = Settings(_env_file=None)
    assert settings.bench_deberta_model == "protectai/deberta-v3-base-prompt-injection-v2"
    assert settings.bench_llamaguard_model == "llama-guard3:1b"
    assert settings.mlflow_tracking_uri == "file:./mlruns"
    assert settings.lakera_api_key is None


def test_lakera_key_is_read_under_its_vendor_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LAKERA_API_KEY", "k-test")
    settings = Settings(_env_file=None)
    assert settings.lakera_api_key is not None
    assert settings.lakera_api_key.get_secret_value() == "k-test"
    # SecretStr keeps the key out of reprs and therefore out of logs.
    assert "k-test" not in repr(settings)


def test_warmup_cannot_be_negative(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIGIE_BENCH_WARMUP_CALLS", "-1")
    with pytest.raises(ValueError):
        Settings(_env_file=None)
