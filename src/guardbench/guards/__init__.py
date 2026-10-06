"""Guard registry: one name on the command line, one adapter built from the settings."""

from __future__ import annotations

from collections.abc import Callable, Sequence

import httpx

from guardbench.guards.base import Guard, GuardUnavailableError, Verdict
from guardbench.guards.deberta import DebertaGuard
from guardbench.guards.gliguard import GliGuard
from guardbench.guards.lakera import LakeraGuard
from guardbench.guards.llamaguard import LlamaGuard
from guardbench.guards.presidio import PresidioGuard
from guardbench.guards.regex import RegexGuard
from vigie.config import Settings

__all__ = ["GUARD_NAMES", "Guard", "GuardUnavailableError", "Verdict", "build_guards"]

_Factory = Callable[[Settings, httpx.Client], Guard]
_FACTORIES: dict[str, _Factory] = {
    "regex": lambda s, c: RegexGuard(),
    "deberta": lambda s, c: DebertaGuard(s.bench_deberta_model, s.guard_input_threshold),
    "gliguard": lambda s, c: GliGuard(s.bench_gliguard_model, s.guard_input_threshold),
    "presidio": lambda s, c: PresidioGuard(s.bench_presidio_entities, s.bench_presidio_threshold),
    "llamaguard": lambda s, c: LlamaGuard(s.ollama_url, s.bench_llamaguard_model, c),
    "lakera": lambda s, c: LakeraGuard(s.lakera_url, s.lakera_api_key, c),
}
GUARD_NAMES: tuple[str, ...] = tuple(_FACTORIES)


def build_guards(names: Sequence[str], settings: Settings, client: httpx.Client) -> list[Guard]:
    unknown = [n for n in names if n not in _FACTORIES]
    if unknown:
        raise ValueError(f"unknown guards {unknown}, choose among {list(GUARD_NAMES)}")
    return [_FACTORIES[name](settings, client) for name in names]
