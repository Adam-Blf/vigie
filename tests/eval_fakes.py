"""An in-memory stand-in for the MlflowClient methods vigie-eval uses, and report builders."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from vigie.evaluation.thresholds import Thresholds, load_thresholds

THRESHOLDS_FILE = Path(__file__).resolve().parents[1] / "eval" / "thresholds.yaml"


def thresholds() -> Thresholds:
    return load_thresholds(THRESHOLDS_FILE)


def report(split: str = "test", llm: str = "fake-llm", **metrics: float | None) -> dict[str, Any]:
    values: dict[str, float | None] = {
        "recall_at_k": 0.85,
        "mrr": 0.70,
        "raw_citation_validity": 0.75,
        "invented_in_final_answer": 0.0,
        "citation_precision": 0.40,
        "citation_coverage": 0.90,
        "correct_refusal_rate": 0.0,
    }
    values.update(metrics)
    return {
        "split": split,
        "llm": llm,
        "config": {
            "embedding_model": "m",
            "embedding_id": "m-123456",
            "sparse_model": "Qdrant/bm25",
            "sparse_language": "french",
            "fusion": "rrf",
            "rrf_k": "60",
            "prefetch_limit": "20",
            "rerank_model": "none",
            "rerank_depth": "0",
            "pin_references": "true",
            "top_k": "6",
            "prompt_version": "v2",
            "ollama_model": "ministral-3:3b-instruct-2512-q4_K_M",
            "corpus_sha256": "ab" * 32,
            "collection": "vigie_m-123456_abababab",
        },
        "metrics": values,
        "ci": {"recall_at_k": {"point": 0.85, "low": 0.7, "high": 0.95}},
    }


@dataclass
class FakeMlflow:
    experiments: dict[str, str] = field(default_factory=dict)
    artifact_locations: dict[str, str | None] = field(default_factory=dict)
    runs: dict[str, dict[str, Any]] = field(default_factory=dict)
    models: dict[str, list[str]] = field(default_factory=dict)
    aliases: dict[tuple[str, str], str] = field(default_factory=dict)

    def get_experiment_by_name(self, name: str) -> Any:
        if name not in self.experiments:
            return None
        return SimpleNamespace(experiment_id=self.experiments[name])

    def create_experiment(self, name: str, artifact_location: str | None = None) -> str:
        self.experiments[name] = str(len(self.experiments) + 1)
        self.artifact_locations[name] = artifact_location
        return self.experiments[name]

    def create_run(
        self, experiment_id: str, tags: dict[str, str] | None = None, run_name: str | None = None
    ) -> Any:
        run_id = f"run{len(self.runs) + 1}"
        self.runs[run_id] = {
            "experiment": experiment_id,
            "name": run_name,
            "tags": tags or {},
            "params": {},
            "metrics": {},
            "artifacts": {},
            "done": False,
        }
        return SimpleNamespace(info=SimpleNamespace(run_id=run_id))

    def log_param(self, run_id: str, key: str, value: Any) -> None:
        self.runs[run_id]["params"][key] = str(value)

    def log_metric(self, run_id: str, key: str, value: float) -> None:
        self.runs[run_id]["metrics"][key] = value

    def log_dict(self, run_id: str, dictionary: dict[str, Any], artifact_file: str) -> None:
        self.runs[run_id]["artifacts"][artifact_file] = json.loads(json.dumps(dictionary))

    def set_terminated(self, run_id: str) -> None:
        self.runs[run_id]["done"] = True

    def download_artifacts(self, run_id: str, path: str, dst_path: str | None = None) -> str:
        target = Path(dst_path or ".") / Path(path).name
        target.write_text(json.dumps(self.runs[run_id]["artifacts"][path]), encoding="utf-8")
        return str(target)

    def get_registered_model(self, name: str) -> Any:
        if name not in self.models:
            raise KeyError(name)
        return SimpleNamespace(name=name)

    def create_registered_model(self, name: str) -> Any:
        self.models[name] = []
        return SimpleNamespace(name=name)

    def create_model_version(self, name: str, source: str, run_id: str) -> Any:
        self.models[name].append(run_id)
        self.runs[run_id]["source"] = source
        return SimpleNamespace(version=str(len(self.models[name])), run_id=run_id)

    def set_registered_model_alias(self, name: str, alias: str, version: str) -> None:
        self.aliases[(name, alias)] = version

    def delete_registered_model_alias(self, name: str, alias: str) -> None:
        del self.aliases[(name, alias)]

    def get_model_version_by_alias(self, name: str, alias: str) -> Any:
        version = self.aliases[(name, alias)]
        return SimpleNamespace(version=version, run_id=self.models[name][int(version) - 1])
