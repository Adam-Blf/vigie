"""One MLflow run per measured variant, in a local store the study never commits.

MLflow is an optional extra (``tracking``). The module is passed in, or imported on first
use, so the unit tests can hand in a recorder instead of writing an mlruns directory.
"""

from __future__ import annotations

import importlib
from collections.abc import Mapping
from pathlib import Path
from typing import Any

EXPERIMENT = "vigie-quantization"
_SQLITE = "sqlite:///"


def log_run(
    run_name: str,
    params: Mapping[str, str | int | float],
    metrics: Mapping[str, float],
    *,
    tracking_uri: str,
    experiment: str = EXPERIMENT,
    mlflow: Any = None,
) -> str:
    """Record params and metrics under ``experiment`` and return the run id."""
    client = mlflow if mlflow is not None else importlib.import_module("mlflow")
    if tracking_uri.startswith(_SQLITE):
        # SQLite creates the database file, not the directory it sits in.
        Path(tracking_uri[len(_SQLITE) :]).parent.mkdir(parents=True, exist_ok=True)
    client.set_tracking_uri(tracking_uri)
    client.set_experiment(experiment)
    with client.start_run(run_name=run_name) as run:
        client.log_params(dict(params))
        client.log_metrics(dict(metrics))
        run_id: str = run.info.run_id
    return run_id
