"""The one place that builds a real MlflowClient.

tracking.py and registry.py each type the handful of client methods they call, so their
tests run against a small in-memory fake. MLflow annotates those methods more loosely
than the protocols do, hence the cast: the calls are the same, only the hints differ.
"""

from __future__ import annotations

from typing import Protocol, cast

from vigie.evaluation.registry import RegistryClient
from vigie.evaluation.tracking import TrackingClient, prepare_sqlite


class MlflowLike(TrackingClient, RegistryClient, Protocol):
    """Both halves of the client: logging runs and managing the registered model."""


def open_client(tracking_uri: str) -> MlflowLike:
    prepare_sqlite(tracking_uri)
    from mlflow import MlflowClient

    return cast(MlflowLike, MlflowClient(tracking_uri=tracking_uri))
