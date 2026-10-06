import json
from collections.abc import Mapping
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from quant_fixtures import CHUNKS, KeywordEncoder, StepClock, question
from vigie.corpus.jsonl import write_chunks
from vigie.quant.decision import QuantThreshold
from vigie.quant.runner import embedding_payload, run_embedding_study, write_json
from vigie.quant.study import StudySettings, load_chunks, measure_variant, top_passages
from vigie.quant.tracking import log_run

THRESHOLD = QuantThreshold(split="dev", k=5, max_recall_drop=0.02, max_size_ratio=0.5)
QUESTIONS = [
    question("dora-1", "qui assure la direction du risque tic ?", ("DORA:5",)),
    question("rgpd-1", "quelle sanction pour les donnees ?", ("RGPD:83",)),
    question("dora-2", "un prestataire tic", ("DORA:28",)),
]
SETTINGS = StudySettings(k=5, warmup=1, passes=2)


def test_measure_variant_times_each_query_and_scores_the_first_pass() -> None:
    encoder = KeywordEncoder()
    result = measure_variant(
        "fp32", encoder, 1000, CHUNKS, QUESTIONS, SETTINGS, clock=StepClock(0.004)
    )
    assert result.recall_at_k == 1.0
    assert result.mrr == 1.0
    assert result.latency_p50_ms == pytest.approx(4.0)
    assert result.questions == 3
    # One call for the corpus, then one per question and pass.
    assert encoder.calls == 1 + 3 * 2


def test_load_chunks_reads_every_jsonl_file(tmp_path: Path) -> None:
    write_chunks(tmp_path / "DORA.jsonl", CHUNKS[:3])
    write_chunks(tmp_path / "RGPD.jsonl", CHUNKS[3:])
    assert load_chunks(tmp_path) == CHUNKS


def test_load_chunks_asks_for_ingestion_when_the_corpus_is_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="vigie-ingest"):
        load_chunks(tmp_path)


def test_top_passages_turn_the_best_chunks_into_rag_passages() -> None:
    encoder = KeywordEncoder()
    documents = encoder.encode([c.text for c in CHUNKS])
    passages = top_passages(encoder.encode(["sanction donnees"])[0], documents, CHUNKS, 2)
    assert [p.article_id for p in passages] == ["RGPD:83", "DORA:5"]
    assert passages[0].score >= passages[1].score
    assert passages[0].url == CHUNKS[3].url


class Recorder:
    def __init__(self) -> None:
        self.runs: list[tuple[str, Mapping[str, Any], Mapping[str, float]]] = []

    def __call__(self, name: str, params: Mapping[str, Any], metrics: Mapping[str, float]) -> str:
        self.runs.append((name, params, metrics))
        return name


def test_embedding_study_logs_both_variants_and_decides() -> None:
    recorder = Recorder()
    variants = {"fp32": (KeywordEncoder(), 400), "int8": (KeywordEncoder(), 100)}
    results, decision = run_embedding_study(
        variants, CHUNKS, QUESTIONS, THRESHOLD, SETTINGS, recorder
    )
    assert [name for name, _, _ in recorder.runs] == ["embedding-fp32", "embedding-int8"]
    assert recorder.runs[1][2]["size_mb"] == 100 / 1e6
    assert decision.deployed == "int8"
    payload = embedding_payload(results, decision, THRESHOLD)
    assert payload["decision"]["size_ratio"] == 0.25
    assert payload["variants"]["fp32"]["questions"] == 3
    assert payload["threshold"]["split"] == "dev"


def test_embedding_study_needs_exactly_the_two_variants() -> None:
    with pytest.raises(ValueError, match="exactly the fp32 and int8"):
        run_embedding_study({"fp32": (KeywordEncoder(), 1)}, CHUNKS, QUESTIONS, THRESHOLD, SETTINGS)


def test_write_json_is_stable_and_utf8(tmp_path: Path) -> None:
    path = tmp_path / "out" / "r.json"
    write_json(path, {"b": 1, "a": "é"})
    text = path.read_text(encoding="utf-8")
    assert text.endswith("\n")
    assert text.index('"a"') < text.index('"b"')
    assert json.loads(text) == {"a": "é", "b": 1}


class FakeMlflow:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []

    def __getattr__(self, name: str) -> Any:
        def record(*args: Any, **kwargs: Any) -> None:
            self.calls.append((name, args or kwargs))

        return record

    def start_run(self, run_name: str) -> Any:
        self.calls.append(("start_run", run_name))
        run = SimpleNamespace(info=SimpleNamespace(run_id="r1"))

        class Context:
            def __enter__(self) -> Any:
                return run

            def __exit__(self, *exc: object) -> None:
                return None

        return Context()


def test_log_run_writes_params_and_metrics_in_one_run(tmp_path: Path) -> None:
    fake = FakeMlflow()
    uri = f"sqlite:///{(tmp_path / 'runs' / 'mlflow.db').as_posix()}"
    run_id = log_run("embedding-int8", {"k": 5}, {"mrr": 0.4}, tracking_uri=uri, mlflow=fake)
    assert run_id == "r1"
    assert (tmp_path / "runs").is_dir()
    names = [name for name, _ in fake.calls]
    assert names == ["set_tracking_uri", "set_experiment", "start_run", "log_params", "log_metrics"]


def test_log_run_leaves_non_sqlite_stores_alone(tmp_path: Path) -> None:
    fake = FakeMlflow()
    log_run("x", {}, {}, tracking_uri="http://127.0.0.1:5000", mlflow=fake)
    assert fake.calls[0] == ("set_tracking_uri", ("http://127.0.0.1:5000",))
