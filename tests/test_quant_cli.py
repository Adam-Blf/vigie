import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from quant_fixtures import CHUNKS, FakeOllama, KeywordEncoder, question
from vigie.config import Settings
from vigie.corpus.jsonl import write_chunks
from vigie.evaluation.golden import dump_golden
from vigie.quant import cli
from vigie.quant.llm_bench import OllamaProbe
from vigie.quant.report import chart_series

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    write_chunks(tmp_path / "corpus" / "DORA.jsonl", CHUNKS)
    rows = [question(f"dora-{i:02d}", "direction du risque tic", ("DORA:5",)) for i in range(12)]
    rows.append(question("sealed", "direction", ("DORA:5",), split="test"))
    (tmp_path / "golden.jsonl").write_text(dump_golden(rows), encoding="utf-8")
    models = tmp_path / "models"
    models.mkdir()
    (models / "model-fp32.onnx").write_bytes(b"x" * 400)
    (models / "model-int8.onnx").write_bytes(b"x" * 100)
    monkeypatch.setattr(cli, "_encoder", lambda *args: KeywordEncoder())
    return tmp_path


def common_args(root: Path) -> list[str]:
    return [
        "--models",
        str(root / "models"),
        "--golden",
        str(root / "golden.jsonl"),
        "--corpus",
        str(root / "corpus"),
        "--no-mlflow",
    ]


def test_parser_defaults_follow_the_settings() -> None:
    settings = Settings(_env_file=None)
    args = cli.build_parser(settings).parse_args(["embed"])
    assert args.thresholds == Path("eval/thresholds.yaml")
    assert args.models == Path("data/quant")
    assert args.results == Path("docs/proofs/J12/embedding-results.json")
    assert not args.no_mlflow


def test_embed_writes_results_and_ignores_the_test_split(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = workspace / "embedding.json"
    thresholds = ROOT / "eval" / "thresholds.yaml"
    argv = ["embed", *common_args(workspace), "--thresholds", str(thresholds)]
    assert cli.main([*argv, "--results", str(out)]) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["variants"]["int8"]["questions"] == 12
    assert payload["decision"]["deployed"] == "int8"
    assert "decision: deploy int8" in capsys.readouterr().out


def test_llm_compares_every_requested_tag(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeOllama()

    def probe(base_url: str, options: dict[str, Any], timeout_s: float) -> OllamaProbe:
        return OllamaProbe(base_url, options, timeout_s, transport=httpx.MockTransport(fake))

    monkeypatch.setattr(cli, "OllamaProbe", probe)
    monkeypatch.setenv("VIGIE_QUANT_LLM_QUESTIONS", "3")
    cli.get_settings.cache_clear()
    out = workspace / "llm.json"
    try:
        argv = ["llm", *common_args(workspace), "--model", "a:q4", "--model", "a:q8"]
        assert cli.main([*argv, "--results", str(out)]) == 0
    finally:
        cli.get_settings.cache_clear()
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert list(payload["variants"]) == ["a:q4", "a:q8"]
    assert payload["variants"]["a:q8"]["summary"]["questions"] == 3
    assert len(payload["variants"]["a:q4"]["answers"]) == 3


def test_chart_series_converts_units_for_the_figure() -> None:
    payload = {
        "variants": {
            "fp32": {
                "size_bytes": 471_191_747,
                "latency_p95_ms": 80.71,
                "recall_at_k": 0.468,
                "mrr": 0.4166,
            },
        }
    }
    assert chart_series(payload)["fp32"] == {
        "Taille (Mo)": 471.2,
        "Latence p95 (ms)": 80.7,
        "Rappel@5 (%)": 46.8,
        "MRR (%)": 41.7,
    }
