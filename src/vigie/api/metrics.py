"""Prometheus metrics of the API.

Every series carries bundle_version: the canary analysis compares the challenger with the
champion, and without that label both would land in the same series. LLM failures have
their own counter, kept out of the error rate the analysis watches, because a full Ollama
queue says the VM is busy, not that the new version is broken.

Each app owns its registry, so tests can build as many apps as they like.
"""

from __future__ import annotations

from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest

LATENCY_BUCKETS = (0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0)
GUARD_BUCKETS = (0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.2, 0.5, 1.0)


class ApiMetrics:
    def __init__(self, bundle_version: str) -> None:
        self.bundle_version = bundle_version
        self.registry = CollectorRegistry()
        labels = ["bundle_version"]
        self.requests = Counter(
            "vigie_requests",
            "HTTP requests by route and status",
            [*labels, "route", "status"],
            registry=self.registry,
        )
        self.latency = Histogram(
            "vigie_request_latency_seconds",
            "End-to-end latency of the API routes",
            [*labels, "route"],
            buckets=LATENCY_BUCKETS,
            registry=self.registry,
        )
        self.blocked = Counter(
            "vigie_blocked",
            "Questions stopped by the input guard",
            [*labels, "reason"],
            registry=self.registry,
        )
        self.refused = Counter(
            "vigie_refused", "Answers ending in a refusal", labels, registry=self.registry
        )
        self.citations_removed = Counter(
            "vigie_citations_removed",
            "Citations removed because no retrieved passage backs them",
            labels,
            registry=self.registry,
        )
        self.errors = Counter(
            "vigie_errors",
            "Server-side failures of the API itself, injected faults included",
            [*labels, "kind"],
            registry=self.registry,
        )
        self.llm_errors = Counter(
            "vigie_llm_errors",
            "LLM failures: full queue, timeout, unreachable provider",
            [*labels, "kind"],
            registry=self.registry,
        )
        self.guard_latency = Histogram(
            "vigie_guard_latency_seconds",
            "Time spent in the input guard chain",
            labels,
            buckets=GUARD_BUCKETS,
            registry=self.registry,
        )

    def render(self) -> bytes:
        return generate_latest(self.registry)
