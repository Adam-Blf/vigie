"""docs/openapi.json is the contract the interface is built against; it must match the code."""

import json
from pathlib import Path

import pytest

from vigie.api import contract

ROOT = Path(__file__).resolve().parent.parent
CONTRACT = ROOT / "docs" / "openapi.json"


def test_published_contract_matches_the_code() -> None:
    published = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert published == contract.openapi_document()


def test_contract_holds_the_fields_the_interface_relies_on() -> None:
    schemas = json.loads(CONTRACT.read_text(encoding="utf-8"))["components"]["schemas"]
    answer = set(schemas["AskResponse"]["properties"])
    assert {
        "answer",
        "citations",
        "blocked",
        "block_reason",
        "refused",
        "trace_id",
        "app_version",
        "bundle_version",
        "model",
        "latency_ms",
    } <= answer
    citation = set(schemas["CitationOut"]["properties"])
    assert citation == {"label", "regulation", "article", "paragraph", "excerpt", "url"}
    reasons = schemas["AskResponse"]["properties"]["block_reason"]["anyOf"][0]["enum"]
    assert reasons == ["injection", "jailbreak", "prompt_leak", "pii", "other"]
    question = schemas["AskRequest"]["properties"]["question"]
    assert (question["minLength"], question["maxLength"]) == (1, 2000)


def test_contract_documents_errors_and_streaming() -> None:
    paths = json.loads(CONTRACT.read_text(encoding="utf-8"))["paths"]
    for code in ("401", "413", "422", "429", "503"):
        assert code in paths["/v1/ask"]["post"]["responses"]
    assert "text/event-stream" in paths["/v1/ask/stream"]["post"]["responses"]["200"]["content"]
    assert "/metrics" not in paths


def test_check_mode_detects_a_stale_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "openapi.json"
    assert contract.main(["--check"], path=target) == 1
    assert contract.main([], path=target) == 0
    assert contract.main(["--check"], path=target) == 0
    assert "out of date" in capsys.readouterr().out
