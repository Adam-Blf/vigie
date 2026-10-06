import sys
from pathlib import Path
from types import ModuleType

import pytest
from tests.eval_fakes import FakeMlflow, report, thresholds
from tests.retrieval_fixtures import MINI_CORPUS

from vigie.config import Settings
from vigie.evaluation import tracking
from vigie.evaluation.bundle import build_bundle, run_config
from vigie.evaluation.gate import run_gate
from vigie.evaluation.mlflow_client import open_client
from vigie.evaluation.registry import (
    BUNDLE_ARTIFACT,
    GateFailedError,
    alias_report,
    register_version,
    remove_alias,
    run_report,
    set_alias,
    show_aliases,
)
from vigie.evaluation.tracking import (
    REPORT_ARTIFACT,
    flat_metrics,
    local_artifact_location,
    log_report,
)
from vigie.retrieval.index import corpus_sha256

SETTINGS = Settings(_env_file=None)


def test_run_config_flattens_everything_that_shapes_an_answer(tmp_path: Path) -> None:
    seal = tmp_path / "test.sha256"
    seal.write_text("abc  test split\n", encoding="utf-8")
    settings = Settings(_env_file=None, golden_seal_path=seal, rerank_model="jina")
    config = run_config(
        settings, embedding_id="e-1", collection="c", chunks=MINI_CORPUS, llm="fake", depth=20
    )
    assert config["corpus_sha256"] == corpus_sha256(MINI_CORPUS)
    assert (config["rerank_model"], config["rerank_depth"]) == ("jina", "30")
    assert (config["golden_test_seal"], config["chunks"], config["prompt_version"]) == (
        "abc",
        "5",
        "v2",
    )
    assert all(isinstance(v, str) for v in config.values())
    bare = run_config(
        Settings(_env_file=None, golden_seal_path=tmp_path / "none"),
        embedding_id="e",
        collection="c",
        chunks=MINI_CORPUS,
        llm="fake",
        depth=20,
    )
    assert (bare["rerank_model"], bare["rerank_depth"], bare["golden_test_seal"]) == (
        "none",
        "0",
        "none",
    )


def test_the_bundle_pins_what_production_needs() -> None:
    bundle = build_bundle(report(), SETTINGS, "3")
    assert bundle["version"] == "3"
    assert bundle["embedding"]["fingerprint"] == "m-123456"
    assert bundle["retrieval"]["rerank_model"] == ""
    assert bundle["retrieval"]["top_k"] == 6
    assert bundle["llm"]["model"] == "ministral-3:3b-instruct-2512-q4_K_M"
    assert bundle["guard"]["input_threshold"] == SETTINGS.guard_input_threshold
    assert bundle["qdrant_collection"] == "vigie_m-123456_abababab"
    assert bundle["fault_injection"] == {"error_rate": 0.0}
    with_reranker = report()
    with_reranker["config"]["rerank_model"] = "jina"
    assert build_bundle(with_reranker, SETTINGS, "4")["retrieval"]["rerank_model"] == "jina"


def test_log_report_creates_the_experiment_once_and_logs_params_metrics_report() -> None:
    client = FakeMlflow()
    first = log_report(client, "vigie-eval", report(), run_name="a", artifact_location="file:///x")
    second = log_report(client, "vigie-eval", report(), run_name="b")
    assert client.experiments == {"vigie-eval": "1"}
    assert client.artifact_locations["vigie-eval"] == "file:///x"
    run = client.runs[first]
    assert run["params"]["embedding_id"] == "m-123456" and run["params"]["split"] == "test"
    assert run["metrics"]["recall_at_k_ci_low"] == 0.7
    assert "correct_refusal_rate" in run["metrics"]
    assert run["artifacts"][REPORT_ARTIFACT]["split"] == "test"
    assert run["done"] and second != first


def test_flat_metrics_skips_missing_values() -> None:
    metrics = flat_metrics(report(correct_refusal_rate=None))
    assert "correct_refusal_rate" not in metrics
    assert metrics["recall_at_k_ci_high"] == 0.95


def test_local_store_folders(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert local_artifact_location("http://127.0.0.1:5000", tmp_path / "a") is None
    location = local_artifact_location("sqlite:///x.db", tmp_path / "a")
    assert location is not None and location.startswith("file:")
    assert (tmp_path / "a").is_dir()
    monkeypatch.chdir(tmp_path)
    fake = ModuleType("mlflow")
    fake.MlflowClient = lambda tracking_uri: ("client", tracking_uri)  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "mlflow", fake)
    assert open_client("sqlite:///store/mlflow.db") == ("client", "sqlite:///store/mlflow.db")
    assert (tmp_path / "store").is_dir()
    tracking.prepare_sqlite("http://server")


def test_a_version_is_only_registered_when_the_gate_passed() -> None:
    client = FakeMlflow()
    run_id = log_report(client, "vigie-eval", report(recall_at_k=0.5), run_name="bad")
    red = run_gate(run_report(client, run_id), thresholds())
    with pytest.raises(GateFailedError):
        register_version(client, "vigie-rag", run_id, report(), red, SETTINGS)
    with pytest.raises(GateFailedError):
        register_version(client, "vigie-rag", run_id, report(), [], SETTINGS)
    assert client.models == {}


def test_register_stores_the_bundle_and_aliases_move() -> None:
    client = FakeMlflow()
    run_id = log_report(client, "vigie-eval", report(), run_name="good")
    green = run_gate(run_report(client, run_id), thresholds())
    version, bundle = register_version(client, "vigie-rag", run_id, report(), green, SETTINGS)
    assert version == "1" and bundle["version"] == "1"
    assert client.runs[run_id]["source"] == f"runs:/{run_id}/bundle"
    assert client.runs[run_id]["artifacts"][BUNDLE_ARTIFACT]["qdrant_collection"]

    assert alias_report(client, "vigie-rag", "champion") is None
    assert show_aliases(client, "vigie-rag") == {"champion": None, "challenger": None}
    set_alias(client, "vigie-rag", "champion", version)
    assert alias_report(client, "vigie-rag", "champion") == report()
    second, _ = register_version(client, "vigie-rag", run_id, report(), green, SETTINGS)
    set_alias(client, "vigie-rag", "challenger", second)
    assert show_aliases(client, "vigie-rag") == {"champion": "1", "challenger": "2"}
    remove_alias(client, "vigie-rag", "challenger")
    assert show_aliases(client, "vigie-rag")["challenger"] is None
    with pytest.raises(ValueError, match="alias"):
        set_alias(client, "vigie-rag", "production", "1")
    with pytest.raises(ValueError, match="alias"):
        remove_alias(client, "vigie-rag", "production")
