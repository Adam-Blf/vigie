import json
import logging
from pathlib import Path

import numpy as np
import pytest
from prometheus_client import CollectorRegistry

from drift_fakes import HashingEmbedder, cluster, load_questions, thresholds
from vigie.config import Settings
from vigie.drift.metrics import DriftMetrics
from vigie.drift.monitor import DriftMonitor, DriftReport, DriftThresholds
from vigie.drift.reference import ReferenceSet

DIM = 16


def _in_scope(count_per_topic: int, seed: int) -> np.ndarray:
    return np.vstack([cluster(axis, count_per_topic, DIM, seed + axis) for axis in range(4)])


def _reference() -> ReferenceSet:
    return ReferenceSet(questions=_in_scope(10, seed=0), anchors=np.eye(DIM)[:4])


def _monitor(**kwargs: object) -> DriftMonitor:
    options: dict[str, object] = {"window_size": 200, "evaluate_every": 1000}
    options.update(kwargs)
    return DriftMonitor(_reference(), thresholds(), **options)  # type: ignore[arg-type]


def test_thresholds_follow_the_settings() -> None:
    settings = Settings(_env_file=None, drift_ks_alpha=0.05, drift_min_window=12)
    loaded = DriftThresholds.from_settings(settings)
    assert loaded.ks_alpha == 0.05
    assert loaded.min_window == 12
    assert loaded.centroid_distance == settings.drift_centroid_threshold


def test_a_small_window_is_not_judged() -> None:
    monitor = _monitor()
    monitor.record(cluster(9, 5, DIM))
    report = monitor.evaluate()
    assert not report.ready
    assert not report.alert
    assert report.to_dict()["indicators"] is None


def test_in_scope_traffic_stays_quiet() -> None:
    monitor = _monitor()
    monitor.record(_in_scope(10, seed=100))
    report = monitor.evaluate()
    assert report.ready
    assert not report.alert, report.to_dict()


def test_off_topic_traffic_trips_every_indicator() -> None:
    monitor = _monitor()
    monitor.record(cluster(9, 40, DIM))
    report = monitor.evaluate()
    assert report.alert
    assert report.reasons == ("centroid_distance", "out_of_scope_ratio", "ks_test")


def test_a_minority_of_off_topic_questions_is_caught_by_the_ratio() -> None:
    monitor = _monitor()
    monitor.record(np.vstack([_in_scope(10, seed=200), cluster(9, 15, DIM)]))
    report = monitor.evaluate()
    assert "out_of_scope_ratio" in report.reasons


def test_alert_is_logged_once_per_incident_then_recovery(
    caplog: pytest.LogCaptureFixture,
) -> None:
    monitor = _monitor(window_size=40)
    caplog.set_level(logging.INFO, logger="vigie.drift")

    monitor.record(cluster(9, 40, DIM))
    monitor.evaluate()
    monitor.evaluate()
    monitor.record(_in_scope(10, seed=300))
    monitor.evaluate()

    events = [json.loads(record.getMessage()) for record in caplog.records]
    assert [event["event"] for event in events] == ["drift_alert", "drift_recovered"]
    assert caplog.records[0].levelno == logging.WARNING
    assert events[0]["reasons"] == ["centroid_distance", "out_of_scope_ratio", "ks_test"]


def test_gauges_move_on_their_own_every_n_questions() -> None:
    registry = CollectorRegistry()
    metrics = DriftMetrics(registry, bundle_version="dev")
    monitor = _monitor(evaluate_every=20, metrics=metrics)
    labels = {"bundle_version": "dev"}

    monitor.record(cluster(9, 19, DIM))
    assert registry.get_sample_value("vigie_drift_alert", labels) is None
    monitor.record(cluster(9, 1, DIM, seed=1))
    assert registry.get_sample_value("vigie_drift_alert", labels) == 1.0
    assert registry.get_sample_value("vigie_drift_out_of_scope_ratio", labels) == 1.0


def test_gauges_are_published_while_the_evaluation_lock_is_held() -> None:
    held: list[bool] = []

    class SpyMetrics(DriftMetrics):
        def publish(self, report: DriftReport) -> None:
            held.append(monitor._lock.locked())

    monitor = _monitor(metrics=SpyMetrics(CollectorRegistry(), "test"))
    monitor.record(_in_scope(10, seed=3))
    monitor.evaluate()

    assert held == [True]


def test_evaluate_every_must_be_positive() -> None:
    with pytest.raises(ValueError, match="evaluate_every"):
        _monitor(evaluate_every=0)


def test_report_serializes_to_json() -> None:
    monitor = _monitor()
    monitor.record(cluster(9, 40, DIM))
    payload = json.loads(json.dumps(monitor.evaluate().to_dict()))
    assert payload["ready"] is True
    assert payload["window_size"] == 40
    assert payload["thresholds"]["min_window"] == 10
    assert set(payload["indicators"]) == {
        "centroid_distance",
        "out_of_scope_ratio",
        "ks_statistic",
        "ks_pvalue",
    }


def test_monitor_loads_its_reference_from_settings(tmp_path: Path) -> None:
    questions_path = tmp_path / "reference.npy"
    anchors_path = tmp_path / "anchors.npy"
    _reference().save(questions_path, anchors_path)
    settings = Settings(
        _env_file=None,
        drift_reference_path=questions_path,
        drift_anchors_path=anchors_path,
        drift_window_size=64,
        drift_evaluate_every=7,
    )

    monitor = DriftMonitor.from_settings(settings)

    assert monitor.window.max_size == 64
    assert monitor.evaluate_every == 7
    assert monitor.reference.dimension == DIM


def _question_monitor(embedder: HashingEmbedder) -> DriftMonitor:
    data = load_questions()
    reference = ReferenceSet.from_texts(
        embedder,
        questions=[item["text"] for item in data["reference"]],
        anchor_texts=[item["text"] for item in data["corpus_passages"]],
        anchor_groups=[item["regulation"] for item in data["corpus_passages"]],
    )
    # Hashed words share far fewer coordinates than a language model's embeddings, so
    # the similarity scale is lower and the cut-offs are rescaled to it.
    return DriftMonitor(
        reference,
        thresholds(centroid_distance=0.7, out_of_scope_similarity=0.05, min_window=20),
        window_size=100,
        evaluate_every=1000,
    )


def test_cooking_questions_trigger_drift_with_the_fake_embedder() -> None:
    embedder = HashingEmbedder()
    monitor = _question_monitor(embedder)
    monitor.observe(embedder, load_questions()["cooking_batch"])
    report = monitor.evaluate()
    assert report.alert, report.to_dict()
    assert {"out_of_scope_ratio", "ks_test"} <= set(report.reasons)


def test_dora_questions_do_not_trigger_drift_with_the_fake_embedder() -> None:
    embedder = HashingEmbedder()
    monitor = _question_monitor(embedder)
    monitor.observe(embedder, load_questions()["dora_batch"])
    report = monitor.evaluate()
    assert not report.alert, report.to_dict()
