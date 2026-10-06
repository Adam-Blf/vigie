"""Drift report before and after a batch of off-topic questions, with the real model.

Until the admin endpoint lands with the API, this prints the exact body that
``GET /v1/admin/drift`` will return, plus the Prometheus lines it will expose.
The reference comes from the test fixture questions, a stand-in for the golden set.

Usage: python scripts/drift_demo.py
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

from prometheus_client import CollectorRegistry, generate_latest
from pydantic_settings import SettingsConfigDict

from vigie.config import Settings
from vigie.drift import (
    DriftMetrics,
    DriftMonitor,
    DriftThresholds,
    FastEmbedEmbedder,
    ReferenceSet,
)

FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "drift_questions.json"


class DemoSettings(Settings):
    # The demo has to print the same report on any machine, so a local .env is ignored.
    model_config = SettingsConfigDict(env_prefix="VIGIE_", env_file=None, extra="ignore")


def _show(title: str, monitor: DriftMonitor, registry: CollectorRegistry) -> None:
    print(f"== {title} ==")
    print(json.dumps(monitor.evaluate().to_dict(), indent=2, sort_keys=True))
    exposition = generate_latest(registry).decode()
    print("\n".join(line for line in exposition.splitlines() if not line.startswith("#")))
    print()


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, stream=sys.stdout, format="LOG %(levelname)s %(message)s"
    )
    settings = DemoSettings()
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    embedder = FastEmbedEmbedder(settings.dense_model)
    reference = ReferenceSet.from_texts(
        embedder,
        questions=[item["text"] for item in data["reference"]],
        anchor_texts=[item["text"] for item in data["corpus_passages"]],
        anchor_groups=[item["regulation"] for item in data["corpus_passages"]],
    )
    registry = CollectorRegistry()
    monitor = DriftMonitor(
        reference,
        DriftThresholds.from_settings(settings),
        window_size=settings.drift_window_size,
        # Evaluations are triggered by hand below so each step prints exactly once.
        evaluate_every=10_000,
        metrics=DriftMetrics(registry, settings.bundle_version),
    )
    print(f"model={settings.dense_model} reference={len(data['reference'])} questions")
    print()

    monitor.observe(embedder, data["dora_batch"])
    _show(f"before: {len(data['dora_batch'])} DORA questions", monitor, registry)

    monitor.observe(embedder, data["cooking_batch"])
    _show(f"after: + {len(data['cooking_batch'])} cooking questions", monitor, registry)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
