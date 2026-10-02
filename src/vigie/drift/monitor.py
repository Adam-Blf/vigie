"""Glue between the window, the detectors, the gauges and the alert log.

The API records the embedding of every answered question, then reads a
``DriftReport`` from ``GET /v1/admin/drift``. The monitor also re-evaluates on its own
every few questions so the Prometheus gauges move with traffic instead of waiting for
someone to open the admin endpoint.
"""

from __future__ import annotations

import json
import logging
import threading
from collections.abc import Sequence
from dataclasses import asdict, dataclass

from vigie.config import Settings
from vigie.drift.detectors import (
    centroid_cosine_distance,
    ks_two_sample,
    max_similarity,
    out_of_scope_ratio,
)
from vigie.drift.embedder import Embedder, Matrix
from vigie.drift.metrics import DriftMetrics
from vigie.drift.reference import ReferenceSet
from vigie.drift.window import EmbeddingWindow

LOGGER = logging.getLogger("vigie.drift")


@dataclass(frozen=True)
class DriftThresholds:
    centroid_distance: float
    out_of_scope_similarity: float
    out_of_scope_ratio: float
    ks_alpha: float
    min_window: int

    @classmethod
    def from_settings(cls, settings: Settings) -> DriftThresholds:
        return cls(
            centroid_distance=settings.drift_centroid_threshold,
            out_of_scope_similarity=settings.drift_out_of_scope_similarity,
            out_of_scope_ratio=settings.drift_out_of_scope_ratio,
            ks_alpha=settings.drift_ks_alpha,
            min_window=settings.drift_min_window,
        )


@dataclass(frozen=True)
class DriftIndicators:
    centroid_distance: float
    out_of_scope_ratio: float
    ks_statistic: float
    ks_pvalue: float


@dataclass(frozen=True)
class DriftReport:
    window_size: int
    indicators: DriftIndicators | None
    alert: bool
    reasons: tuple[str, ...]
    thresholds: DriftThresholds

    @property
    def ready(self) -> bool:
        """False while the window is too small for the indicators to mean anything."""
        return self.indicators is not None

    def to_dict(self) -> dict[str, object]:
        """JSON-ready shape, the body of ``GET /v1/admin/drift``."""
        return {
            "ready": self.ready,
            "window_size": self.window_size,
            "alert": self.alert,
            "reasons": list(self.reasons),
            "indicators": None if self.indicators is None else asdict(self.indicators),
            "thresholds": asdict(self.thresholds),
        }


def _breaches(indicators: DriftIndicators, thresholds: DriftThresholds) -> tuple[str, ...]:
    reasons: list[str] = []
    if indicators.centroid_distance > thresholds.centroid_distance:
        reasons.append("centroid_distance")
    if indicators.out_of_scope_ratio > thresholds.out_of_scope_ratio:
        reasons.append("out_of_scope_ratio")
    if indicators.ks_pvalue < thresholds.ks_alpha:
        reasons.append("ks_test")
    return tuple(reasons)


class DriftMonitor:
    def __init__(
        self,
        reference: ReferenceSet,
        thresholds: DriftThresholds,
        window_size: int,
        evaluate_every: int = 10,
        metrics: DriftMetrics | None = None,
        logger: logging.Logger = LOGGER,
    ) -> None:
        if evaluate_every < 1:
            raise ValueError("evaluate_every must be at least 1")
        self.reference = reference
        self.thresholds = thresholds
        self.window = EmbeddingWindow(window_size, reference.dimension)
        self.evaluate_every = evaluate_every
        self.metrics = metrics
        self.logger = logger
        self._since_evaluation = 0
        self._alerting = False
        # Requests are served from a thread pool: the window and the alert state must
        # change together or two threads could both log the same rising edge.
        self._lock = threading.Lock()

    @classmethod
    def from_settings(cls, settings: Settings, metrics: DriftMetrics | None = None) -> DriftMonitor:
        reference = ReferenceSet.load(settings.drift_reference_path, settings.drift_anchors_path)
        return cls(
            reference=reference,
            thresholds=DriftThresholds.from_settings(settings),
            window_size=settings.drift_window_size,
            evaluate_every=settings.drift_evaluate_every,
            metrics=metrics,
        )

    def record(self, embeddings: Matrix) -> None:
        """Add production embeddings, re-evaluating every ``evaluate_every`` of them."""
        with self._lock:
            self._since_evaluation += self.window.add(embeddings)
            due = self._since_evaluation >= self.evaluate_every
        if due:
            self.evaluate()

    def observe(self, embedder: Embedder, questions: Sequence[str]) -> None:
        """Embed questions and keep only their vectors; the text goes no further."""
        self.record(embedder.embed(questions))

    def evaluate(self) -> DriftReport:
        with self._lock:
            self._since_evaluation = 0
            report = self._compute()
            # Logging only on transitions keeps one line per incident instead of one
            # per evaluation, which is what an on-call reader actually wants.
            rising = report.alert and not self._alerting
            falling = self._alerting and not report.alert
            self._alerting = report.alert
        if self.metrics is not None:
            self.metrics.publish(report)
        if rising:
            self._log(logging.WARNING, "drift_alert", report)
        elif falling:
            self._log(logging.INFO, "drift_recovered", report)
        return report

    def _compute(self) -> DriftReport:
        window = self.window.matrix()
        size = int(window.shape[0])
        if size < self.thresholds.min_window:
            # A KS test on a handful of points flags noise, so the first questions
            # after start-up never raise an alert on their own.
            return DriftReport(size, None, False, (), self.thresholds)
        similarities = max_similarity(window, self.reference.anchors)
        ks = ks_two_sample(self.reference.baseline_similarity, similarities)
        indicators = DriftIndicators(
            centroid_distance=centroid_cosine_distance(self.reference.centroid, window),
            out_of_scope_ratio=out_of_scope_ratio(
                similarities, self.thresholds.out_of_scope_similarity
            ),
            ks_statistic=ks.statistic,
            ks_pvalue=ks.pvalue,
        )
        reasons = _breaches(indicators, self.thresholds)
        return DriftReport(size, indicators, bool(reasons), reasons, self.thresholds)

    def _log(self, level: int, event: str, report: DriftReport) -> None:
        payload = {"event": event, **report.to_dict()}
        self.logger.log(level, json.dumps(payload, sort_keys=True))
