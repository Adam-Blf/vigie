"""Log an evaluation report to MLflow, as one run of the vigie-eval experiment.

Only the MlflowClient methods used here are typed, so the tests hand in a small fake and
never need a tracking server. The real client is imported lazily: MLflow is an optional
dependency (extra `tracking`), the API image does not ship it and never talks to it.

The local default is a SQLite file under mlruns/, ignored by git. MLflow 3 refuses its
old plain-folder store, and SQLite needs nothing installed besides MLflow itself.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol

REPORT_ARTIFACT = "report/report.json"


class _RunInfo(Protocol):
    @property
    def run_id(self) -> str: ...


class _Run(Protocol):
    @property
    def info(self) -> _RunInfo: ...


class _Experiment(Protocol):
    @property
    def experiment_id(self) -> str: ...


class TrackingClient(Protocol):
    def get_experiment_by_name(self, name: str) -> _Experiment | None: ...

    def create_experiment(self, name: str, artifact_location: str | None = None) -> str: ...

    def create_run(
        self, experiment_id: str, tags: dict[str, str] | None = None, run_name: str | None = None
    ) -> _Run: ...

    def log_param(self, run_id: str, key: str, value: Any) -> Any: ...

    def log_metric(self, run_id: str, key: str, value: float) -> Any: ...

    def log_dict(self, run_id: str, dictionary: dict[str, Any], artifact_file: str) -> Any: ...

    def set_terminated(self, run_id: str) -> Any: ...


def local_artifact_location(tracking_uri: str, artifact_dir: Path) -> str | None:
    """Where a local SQLite store keeps artifacts; a server decides that on its own."""
    if not tracking_uri.startswith("sqlite:"):
        return None
    artifact_dir.mkdir(parents=True, exist_ok=True)
    return artifact_dir.resolve().as_uri()


def prepare_sqlite(tracking_uri: str) -> None:
    """Create the folder of a relative SQLite file; SQLite creates the file, not the folder."""
    prefix = "sqlite:///"
    if tracking_uri.startswith(prefix):
        Path(tracking_uri[len(prefix) :]).parent.mkdir(parents=True, exist_ok=True)


def experiment_id(client: TrackingClient, name: str, artifact_location: str | None) -> str:
    found = client.get_experiment_by_name(name)
    if found is not None:
        return found.experiment_id
    return client.create_experiment(name, artifact_location=artifact_location)


def flat_metrics(report: Mapping[str, Any]) -> dict[str, float]:
    """Point values plus the bounds of every confidence interval, MLflow wants flat keys."""
    metrics = {k: float(v) for k, v in report["metrics"].items() if v is not None}
    for name, interval in report.get("ci", {}).items():
        metrics[f"{name}_ci_low"] = float(interval["low"])
        metrics[f"{name}_ci_high"] = float(interval["high"])
    return metrics


def log_report(
    client: TrackingClient,
    experiment: str,
    report: Mapping[str, Any],
    *,
    run_name: str,
    artifact_location: str | None = None,
) -> str:
    """One run per report: config as parameters, metrics with their intervals, the report."""
    run = client.create_run(
        experiment_id(client, experiment, artifact_location),
        tags={"split": str(report["split"]), "llm": str(report["llm"])},
        run_name=run_name,
    )
    run_id = run.info.run_id
    for key, value in report["config"].items():
        client.log_param(run_id, key, value)
    client.log_param(run_id, "split", report["split"])
    for key, value in flat_metrics(report).items():
        client.log_metric(run_id, key, value)
    client.log_dict(run_id, dict(report), REPORT_ARTIFACT)
    client.set_terminated(run_id)
    return run_id
