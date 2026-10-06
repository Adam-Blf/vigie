"""The contract every guard adapter follows, whatever sits behind it.

A local regex, a transformer, a local LLM and a SaaS API all reduce to the same call:
text in, verdict out. That is what lets the runner time them on equal terms.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


class GuardUnavailableError(RuntimeError):
    """Raised by setup() when a guard cannot run here (missing key, model, or service).

    The runner skips the guard and says why, instead of reporting a guard that never ran
    as one that detected nothing.
    """


@dataclass(frozen=True)
class Verdict:
    flagged: bool
    labels: tuple[str, ...] = field(default_factory=tuple)
    # Confidence that the text is malicious, in [0, 1]. Rule-based guards report 0 or 1.
    score: float = 0.0


class Guard(ABC):
    name: str = "guard"
    # Categories the vendor claims to handle. Scoring a PII detector on jailbreaks would
    # say more about the benchmark than about the tool, so each guard also gets a score
    # restricted to what it announces.
    covers: frozenset[str] = frozenset()

    def setup(self) -> None:  # noqa: B027 - a no-op default, rule-based guards load nothing
        """Load models or check the remote service. Heavy imports belong here."""

    @abstractmethod
    def check(self, text: str) -> Verdict:
        """Classify one text."""
