import json
from pathlib import Path

import pytest
from tests.eval_fakes import FakeMlflow, report
from tests.retrieval_fixtures import FakeEmbedder, indexed_settings
from tests.test_eval_retrieval import question

from vigie.evaluation import cli as eval_cli
from vigie.evaluation import run_cli
from vigie.evaluation.golden import dump_golden
from vigie.retrieval import factory


@pytest.fixture
def mlflow(monkeypatch: pytest.MonkeyPatch) -> FakeMlflow:
    client = FakeMlflow()
    monkeypatch.setattr(run_cli, "open_client", lambda uri: client)
    return client


@pytest.fixture
def golden(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    settings = indexed_settings(tmp_path)
    monkeypatch.setattr(eval_cli, "get_settings", lambda: settings)
    monkeypatch.setattr(run_cli, "get_settings", lambda: settings)
    monkeypatch.setattr(run_cli.FastEmbedEmbedder, "from_settings", lambda s: FakeEmbedder())
    monkeypatch.setattr(factory.FastEmbedEmbedder, "from_settings", lambda s: FakeEmbedder())
    path = tmp_path / "golden.jsonl"
    rows = [
        question("a", ("DORA:28",)),
        question("t", ("DORA:28",), split="test"),
        question("o", (), split="test"),
    ]
    path.write_text(dump_golden(rows), encoding="utf-8")
    return path


def run(golden: Path, out: Path, *extra: str) -> int:
    return eval_cli.main(["run", "--golden", str(golden), "--out", str(out), *extra])


def test_run_writes_the_report_and_logs_one_mlflow_run(
    golden: Path, tmp_path: Path, mlflow: FakeMlflow, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "r" / "report.json"
    assert run(golden, out, "--split", "test", "--run-name", "candidate") == 0
    printed = capsys.readouterr().out
    assert "recall_at_k" in printed and "95 % CI" in printed and "mlflow run: run1" in printed
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert saved["llm"] == "fake-llm"
    assert saved["metrics"]["recall_at_k"] == 1.0
    assert saved["metrics"]["invented_in_final_answer"] == 0
    assert saved["config"]["collection"].startswith("vigie_fake-000000_")
    assert mlflow.runs["run1"]["name"] == "candidate"


def test_run_without_mlflow_or_llm(
    golden: Path, tmp_path: Path, mlflow: FakeMlflow, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "report.json"
    assert run(golden, out, "--no-mlflow", "--llm", "none") == 0
    assert mlflow.runs == {}
    assert set(json.loads(out.read_text(encoding="utf-8"))["metrics"]) == {"recall_at_k", "mrr"}
    assert "llm=none" in capsys.readouterr().out


def test_run_with_the_configured_llm(
    golden: Path, tmp_path: Path, mlflow: FakeMlflow, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The configured provider is the fake one here, so no test ever reaches a real Ollama.
    settings = run_cli.get_settings().model_copy(update={"llm_provider": "fake"})
    monkeypatch.setattr(run_cli, "get_settings", lambda: settings)
    assert run_cli._llm("configured", settings).model == "fake-llm"
    out = tmp_path / "x.json"
    assert run(golden, out, "--no-mlflow", "--llm", "configured") == 0
    assert json.loads(out.read_text(encoding="utf-8"))["llm"] == "fake-llm"


def test_gate_reads_a_baseline_file_or_the_champion(
    golden: Path, tmp_path: Path, mlflow: FakeMlflow, capsys: pytest.CaptureFixture[str]
) -> None:
    good, worse = tmp_path / "good.json", tmp_path / "worse.json"
    good.write_text(json.dumps(report(recall_at_k=0.90)), encoding="utf-8")
    worse.write_text(json.dumps(report(recall_at_k=0.85)), encoding="utf-8")

    assert eval_cli.main(["gate", "--report", str(good)]) == 0
    assert "gate PASSED" in capsys.readouterr().out
    assert eval_cli.main(["gate", "--report", str(worse), "--baseline", str(good)]) == 1
    assert "gate FAILED" in capsys.readouterr().out
    # No champion registered yet: only the floors apply.
    assert eval_cli.main(["gate", "--report", str(worse), "--champion"]) == 0


def test_register_refuses_a_red_run_then_registers_a_green_one(
    golden: Path, tmp_path: Path, mlflow: FakeMlflow, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run(golden, tmp_path / "dev.json") == 0
    assert eval_cli.main(["register", "run1"]) == 1
    assert "not registered" in capsys.readouterr().out
    assert mlflow.models == {}

    assert run(golden, tmp_path / "test.json", "--split", "test") == 0
    assert eval_cli.main(["register", "run2", "--alias", "champion"]) == 0
    printed = capsys.readouterr().out
    assert "registered vigie-rag version 1" in printed and "alias champion -> version 1" in printed


def test_alias_show_set_remove(
    golden: Path, tmp_path: Path, mlflow: FakeMlflow, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run(golden, tmp_path / "test.json", "--split", "test") == 0
    assert eval_cli.main(["register", "run1"]) == 0
    capsys.readouterr()

    assert eval_cli.main(["alias", "set", "challenger"]) == 2
    assert eval_cli.main(["alias", "set", "challenger", "1"]) == 0
    assert "challenger: 1" in capsys.readouterr().out
    assert eval_cli.main(["alias", "remove", "challenger"]) == 0
    assert "challenger: -" in capsys.readouterr().out
    assert eval_cli.main(["alias", "show"]) == 0
    assert "champion: -" in capsys.readouterr().out
