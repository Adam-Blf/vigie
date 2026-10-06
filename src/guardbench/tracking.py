"""MLflow logging, one run per guard, so runs can be compared side by side in the UI."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

from guardbench.runner import GuardRun


def log_runs(
    runs: Sequence[GuardRun],
    tracking_uri: str,
    experiment: str,
    dataset: str,
    artifacts: Sequence[Path] = (),
) -> list[str]:
    import mlflow

    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(experiment)
    run_ids: list[str] = []
    for run in runs:
        with mlflow.start_run(run_name=run.name) as active:
            mlflow.log_params(
                {"guard": run.name, "covers": ",".join(sorted(run.covers)), "dataset": dataset}
            )
            if run.skipped_reason is not None:
                mlflow.set_tag("skipped", run.skipped_reason)
            for scope, metrics in (("overall", run.overall), ("in_scope", run.in_scope)):
                if metrics is None:
                    continue
                values = asdict(metrics)
                by_category = values.pop("by_category")
                mlflow.log_metrics({f"{scope}_{k}": float(v) for k, v in values.items()})
                mlflow.log_metrics({f"{scope}_rate_{k}": v for k, v in by_category.items()})
            mlflow.log_metric("errors", run.errors)
            for artifact in artifacts:
                mlflow.log_artifact(str(artifact))
            run_ids.append(str(active.info.run_id))
    return run_ids
