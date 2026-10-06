"""Prometheus gauges for drift, under the metric names shared with the API.

The registry is injected: the API passes the process registry it serves on the
metrics port, tests pass a fresh one so two monitors never collide on a name.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from prometheus_client import CollectorRegistry, Gauge

if TYPE_CHECKING:
    from vigie.drift.monitor import DriftReport

_LABELS = ("bundle_version",)


class DriftMetrics:
    def __init__(self, registry: CollectorRegistry, bundle_version: str) -> None:
        self.bundle_version = bundle_version
        self.centroid_distance = Gauge(
            "vigie_drift_centroid_distance",
            "Cosine distance between the reference and production question centroids.",
            _LABELS,
            registry=registry,
        )
        self.out_of_scope_ratio = Gauge(
            "vigie_drift_out_of_scope_ratio",
            "Share of recent questions far from every corpus centroid.",
            _LABELS,
            registry=registry,
        )
        self.ks_pvalue = Gauge(
            "vigie_drift_ks_pvalue",
            "KS test p-value, reference versus recent similarity distributions.",
            _LABELS,
            registry=registry,
        )
        self.alert = Gauge(
            "vigie_drift_alert",
            "1 while at least one drift indicator is past its threshold.",
            _LABELS,
            registry=registry,
        )

    def publish(self, report: DriftReport) -> None:
        """Copy a report into the gauges.

        A window too small to judge leaves the indicator gauges untouched, so a
        dashboard keeps the last meaningful value instead of dropping to zero after a
        restart, but the alert gauge always follows the report.
        """
        version = self.bundle_version
        self.alert.labels(version).set(1.0 if report.alert else 0.0)
        indicators = report.indicators
        if indicators is None:
            return
        self.centroid_distance.labels(version).set(indicators.centroid_distance)
        self.out_of_scope_ratio.labels(version).set(indicators.out_of_scope_ratio)
        self.ks_pvalue.labels(version).set(indicators.ks_pvalue)
