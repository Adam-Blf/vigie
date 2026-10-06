from prometheus_client import CollectorRegistry

from drift_fakes import thresholds
from vigie.drift.metrics import DriftMetrics
from vigie.drift.monitor import DriftIndicators, DriftReport

NAMES = (
    "vigie_drift_centroid_distance",
    "vigie_drift_out_of_scope_ratio",
    "vigie_drift_ks_pvalue",
    "vigie_drift_alert",
)


def _value(registry: CollectorRegistry, name: str) -> float | None:
    return registry.get_sample_value(name, {"bundle_version": "v7"})


def test_publish_copies_a_ready_report_into_labelled_gauges() -> None:
    registry = CollectorRegistry()
    metrics = DriftMetrics(registry, bundle_version="v7")
    indicators = DriftIndicators(
        centroid_distance=0.42, out_of_scope_ratio=0.6, ks_statistic=0.9, ks_pvalue=1e-9
    )
    report = DriftReport(50, indicators, True, ("centroid_distance",), thresholds())

    metrics.publish(report)

    assert _value(registry, "vigie_drift_centroid_distance") == 0.42
    assert _value(registry, "vigie_drift_out_of_scope_ratio") == 0.6
    assert _value(registry, "vigie_drift_ks_pvalue") == 1e-9
    assert _value(registry, "vigie_drift_alert") == 1.0


def test_publish_of_a_warming_window_only_moves_the_alert_gauge() -> None:
    registry = CollectorRegistry()
    metrics = DriftMetrics(registry, bundle_version="v7")

    metrics.publish(DriftReport(3, None, False, (), thresholds()))

    assert _value(registry, "vigie_drift_alert") == 0.0
    for name in NAMES[:3]:
        assert _value(registry, name) is None
