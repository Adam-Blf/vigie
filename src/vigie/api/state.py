"""Everything a request handler needs, built once per application.

Tests build this container with a fake model, a static retriever and temporary files;
production builds it from the settings and the bundle. Handlers only see the container,
so no handler can quietly create its own client or read the environment.
"""

from __future__ import annotations

import random
import threading
from collections.abc import Callable
from dataclasses import dataclass, field

from vigie.api.audit import AuditLog
from vigie.api.auth import TokenStore
from vigie.api.bundle import Bundle
from vigie.api.metrics import ApiMetrics
from vigie.api.probes import Probe
from vigie.api.ratelimit import SlidingWindowLimiter
from vigie.api.usage import UsageStore
from vigie.config import Settings
from vigie.drift.monitor import DriftMonitor
from vigie.guard.base import InputGuard
from vigie.rag.pipeline import RagPipeline


@dataclass
class AppState:
    settings: Settings
    bundle: Bundle
    pipeline: RagPipeline
    input_guard: InputGuard
    model: str
    tokens: TokenStore
    usage: UsageStore
    audit: AuditLog
    limiter: SlidingWindowLimiter
    metrics: ApiMetrics
    probes: dict[str, Probe]
    # Drawn once per request to decide an injected fault; a test passes a fixed value.
    random: Callable[[], float] = random.random
    llm_slots: threading.BoundedSemaphore = field(init=False)
    # Called when the app shuts down, to release the LLM client's connection pool.
    on_close: list[Callable[[], None]] = field(default_factory=list)
    # None when the drift reference was not built: /v1/admin/drift then answers 503.
    drift: DriftMonitor | None = None

    def __post_init__(self) -> None:
        self.llm_slots = threading.BoundedSemaphore(self.settings.llm_max_inflight)
