"""End-to-end drift check with the real multilingual MiniLM model.

The thresholds are the production defaults from the settings, untouched: this is the
test that says those defaults separate a regulatory stream from an off-topic one.
"""

import pytest

from drift_fakes import load_questions
from vigie.config import Settings
from vigie.drift.embedder import FastEmbedEmbedder
from vigie.drift.monitor import DriftMonitor, DriftThresholds
from vigie.drift.reference import ReferenceSet

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def settings() -> Settings:
    return Settings(_env_file=None)


@pytest.fixture(scope="module")
def embedder(settings: Settings) -> FastEmbedEmbedder:
    return FastEmbedEmbedder(settings.dense_model)


@pytest.fixture(scope="module")
def reference(embedder: FastEmbedEmbedder) -> ReferenceSet:
    data = load_questions()
    return ReferenceSet.from_texts(
        embedder,
        questions=[item["text"] for item in data["reference"]],
        anchor_texts=[item["text"] for item in data["corpus_passages"]],
        anchor_groups=[item["regulation"] for item in data["corpus_passages"]],
    )


def _monitor(reference: ReferenceSet, settings: Settings) -> DriftMonitor:
    return DriftMonitor(
        reference,
        DriftThresholds.from_settings(settings),
        window_size=settings.drift_window_size,
        evaluate_every=settings.drift_evaluate_every,
    )


def test_real_model_flags_a_batch_of_cooking_questions(
    reference: ReferenceSet, embedder: FastEmbedEmbedder, settings: Settings
) -> None:
    monitor = _monitor(reference, settings)
    monitor.observe(embedder, load_questions()["cooking_batch"])
    report = monitor.evaluate()
    assert report.reasons == ("centroid_distance", "out_of_scope_ratio", "ks_test")


def test_real_model_keeps_a_batch_of_dora_questions_quiet(
    reference: ReferenceSet, embedder: FastEmbedEmbedder, settings: Settings
) -> None:
    monitor = _monitor(reference, settings)
    monitor.observe(embedder, load_questions()["dora_batch"])
    report = monitor.evaluate()
    assert report.ready
    assert not report.alert, report.to_dict()
