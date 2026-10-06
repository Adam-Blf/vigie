import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from api_fixtures import api_settings, make_api
from vigie.api.bundle import BundleError, llm_settings, load_bundle
from vigie.rag.prompt import PROMPT_VERSION


def write_bundle(tmp_path: Path, **overrides: object) -> Path:
    data: dict[str, object] = {
        "bundle_version": "2026.10.06-champion",
        "prompt_version": PROMPT_VERSION,
        "top_k": 4,
        "llm": {"provider": "fake"},
        "guard": {"input_threshold": 0.8},
        "fault_injection": {"error_rate": 0.0},
    }
    data.update(overrides)
    path = tmp_path / "bundle.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_without_file_the_bundle_comes_from_settings(tmp_path: Path) -> None:
    bundle = load_bundle(api_settings(tmp_path, top_k=3, fault_error_rate=0.2))
    assert bundle.bundle_version == "test-bundle"
    assert (bundle.top_k, bundle.fault_injection.error_rate) == (3, 0.2)
    assert bundle.prompt_version == PROMPT_VERSION


def test_file_bundle_drives_the_api(tmp_path: Path) -> None:
    api = make_api(tmp_path, bundle_path=write_bundle(tmp_path))
    body = api.ask().json()
    assert body["bundle_version"] == "2026.10.06-champion"
    assert 'bundle_version="2026.10.06-champion"' in api.client.get("/metrics").text


def test_bundle_for_another_prompt_refuses_to_start(tmp_path: Path) -> None:
    settings = api_settings(tmp_path, bundle_path=write_bundle(tmp_path, prompt_version="v0"))
    with pytest.raises(BundleError, match="prompt v0"):
        load_bundle(settings)


def test_unknown_key_in_bundle_is_rejected(tmp_path: Path) -> None:
    settings = api_settings(tmp_path, bundle_path=write_bundle(tmp_path, topk=3))
    with pytest.raises(ValidationError):
        load_bundle(settings)


def test_error_rate_out_of_range_is_rejected(tmp_path: Path) -> None:
    path = write_bundle(tmp_path, fault_injection={"error_rate": 1.5})
    with pytest.raises(ValidationError):
        load_bundle(api_settings(tmp_path, bundle_path=path))


@pytest.mark.parametrize(
    ("llm", "field", "value"),
    [
        (
            {"provider": "ollama", "model": "ministral-3:3b-q8_0"},
            "ollama_model",
            "ministral-3:3b-q8_0",
        ),
        ({"provider": "mistral", "model": "ministral-8b"}, "mistral_model", "ministral-8b"),
    ],
)
def test_bundle_model_overrides_the_settings(
    tmp_path: Path, llm: dict[str, str], field: str, value: str
) -> None:
    settings = api_settings(tmp_path, bundle_path=write_bundle(tmp_path, llm=llm))
    applied = llm_settings(settings, load_bundle(settings))
    assert applied.llm_provider == llm["provider"]
    assert getattr(applied, field) == value


def test_bundle_without_model_keeps_the_settings_tag(tmp_path: Path) -> None:
    settings = api_settings(tmp_path)
    assert llm_settings(settings, load_bundle(settings)).ollama_model == settings.ollama_model
