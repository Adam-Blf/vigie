"""Assembles an AppState from the settings, the bundle and the chosen components.

The guard and the retriever are passed in rather than built here: production picks them
from the configuration (see vigie.api.__main__), tests pass light stand-ins, and neither
needs the other's dependencies installed.
"""

from __future__ import annotations

from vigie.api.audit import AuditLog
from vigie.api.auth import TokenStore
from vigie.api.bundle import llm_settings, load_bundle
from vigie.api.metrics import ApiMetrics
from vigie.api.probes import llm_probe, retriever_probe
from vigie.api.ratelimit import SlidingWindowLimiter
from vigie.api.state import AppState
from vigie.api.usage import UsageStore
from vigie.config import Settings
from vigie.drift.metrics import DriftMetrics
from vigie.drift.monitor import DriftMonitor
from vigie.guard.base import InputGuard
from vigie.llm.base import LLMClient
from vigie.llm.factory import build_llm
from vigie.rag.pipeline import RagPipeline, Retriever


def build_state(
    settings: Settings,
    *,
    input_guard: InputGuard,
    retriever: Retriever,
    llm: LLMClient | None = None,
    drift: DriftMonitor | None = None,
) -> AppState:
    bundle = load_bundle(settings)
    client = llm if llm is not None else build_llm(llm_settings(settings, bundle))
    pipeline = RagPipeline(
        retriever,
        client,
        top_k=bundle.top_k,
        min_score=settings.rag_min_score,
        require_citation=settings.rag_require_citation,
    )
    metrics = ApiMetrics(bundle.bundle_version)
    if drift is not None:
        # The drift gauges join the API registry, so one scrape of /metrics carries both.
        drift.metrics = DriftMetrics(metrics.registry, bundle.bundle_version)
    return AppState(
        settings=settings,
        bundle=bundle,
        pipeline=pipeline,
        input_guard=input_guard,
        model=client.model,
        tokens=TokenStore(settings.db_path, settings.token_ttl_days, settings.usage_retention_days),
        usage=UsageStore(
            settings.db_path,
            settings.usage_cost_per_1k_tokens_eur,
            settings.usage_retention_days,
        ),
        audit=AuditLog(settings.audit_dir, settings.audit_pod_name, settings.audit_retention_days),
        limiter=SlidingWindowLimiter(settings.rate_limit_per_minute),
        metrics=metrics,
        probes={"retriever": retriever_probe(settings), "llm": llm_probe(settings, bundle)},
        on_close=[client.close],
        drift=drift,
    )
