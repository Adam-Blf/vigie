"""Registered model `vigie-rag`: versions that passed the gate, and the two aliases.

A version points at the evaluation run that justified it and holds `bundle/bundle.json`,
the settings production applies. `champion` names the version in production, `challenger`
the one under canary (brief, section 11.8). A CD step reads the aliases and writes the
ConfigMaps; the API itself never contacts MLflow.
"""

from __future__ import annotations

import json
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Protocol

from vigie.config import Settings
from vigie.evaluation.bundle import build_bundle
from vigie.evaluation.gate import Check, passed
from vigie.evaluation.tracking import REPORT_ARTIFACT

ALIASES = ("champion", "challenger")
BUNDLE_ARTIFACT = "bundle/bundle.json"


class _Version(Protocol):
    @property
    def version(self) -> str: ...

    @property
    def run_id(self) -> str: ...


class RegistryClient(Protocol):
    def get_registered_model(self, name: str) -> Any: ...

    def create_registered_model(self, name: str) -> Any: ...

    def create_model_version(self, name: str, source: str, run_id: str) -> _Version: ...

    def log_dict(self, run_id: str, dictionary: dict[str, Any], artifact_file: str) -> Any: ...

    def download_artifacts(self, run_id: str, path: str, dst_path: str | None = None) -> str: ...

    def set_registered_model_alias(self, name: str, alias: str, version: str) -> None: ...

    def delete_registered_model_alias(self, name: str, alias: str) -> None: ...

    def get_model_version_by_alias(self, name: str, alias: str) -> _Version: ...


class GateFailedError(RuntimeError):
    """Registration was asked for a run that does not pass the evaluation gate."""


def run_report(client: RegistryClient, run_id: str) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as folder:
        local = client.download_artifacts(run_id, REPORT_ARTIFACT, folder)
        report: dict[str, Any] = json.loads(Path(local).read_text(encoding="utf-8"))
    return report


def alias_report(client: RegistryClient, name: str, alias: str) -> dict[str, Any] | None:
    """The report behind an alias, None when the model or the alias does not exist yet."""
    try:
        version = client.get_model_version_by_alias(name, alias)
    except Exception:  # MLflow raises its own RestException; the fake raises KeyError.
        return None
    return run_report(client, version.run_id)


def _ensure_model(client: RegistryClient, name: str) -> None:
    try:
        client.get_registered_model(name)
    except Exception:
        client.create_registered_model(name)


def register_version(
    client: RegistryClient,
    name: str,
    run_id: str,
    report: dict[str, Any],
    checks: Sequence[Check],
    settings: Settings,
) -> tuple[str, dict[str, Any]]:
    """Create a version for a run whose gate passed, and store its bundle in the run."""
    if not checks or not passed(list(checks)):
        raise GateFailedError("the evaluation gate did not pass, nothing was registered")
    _ensure_model(client, name)
    version = client.create_model_version(name, f"runs:/{run_id}/bundle", run_id)
    bundle = build_bundle(report, settings, str(version.version))
    client.log_dict(run_id, bundle, BUNDLE_ARTIFACT)
    return str(version.version), bundle


def set_alias(client: RegistryClient, name: str, alias: str, version: str) -> None:
    if alias not in ALIASES:
        raise ValueError(f"alias must be one of {', '.join(ALIASES)}")
    client.set_registered_model_alias(name, alias, version)


def remove_alias(client: RegistryClient, name: str, alias: str) -> None:
    if alias not in ALIASES:
        raise ValueError(f"alias must be one of {', '.join(ALIASES)}")
    client.delete_registered_model_alias(name, alias)


def show_aliases(client: RegistryClient, name: str) -> dict[str, str | None]:
    found: dict[str, str | None] = {}
    for alias in ALIASES:
        try:
            found[alias] = str(client.get_model_version_by_alias(name, alias).version)
        except Exception:
            found[alias] = None
    return found
