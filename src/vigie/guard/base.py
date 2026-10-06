"""What the API needs from a guardrail, whatever runs behind it.

The API never talks to a regex or a classifier directly. It hands the normalized question
to an input guard and gets a decision with a reason it can show and count. That keeps the
choice of detectors a configuration of the guard package, measured by the benchmark,
instead of something spread across the request handlers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol

# The reasons the interface knows how to explain. A detector label that maps to none of
# them is still a block, reported as "other" rather than dropped.
BlockReason = Literal["injection", "jailbreak", "prompt_leak", "pii", "other"]

# When a text trips several detectors, the most serious one is reported. PII comes last:
# a question that is both an attack and contains an e-mail is first of all an attack.
REASON_PRIORITY: tuple[BlockReason, ...] = (
    "injection",
    "jailbreak",
    "prompt_leak",
    "other",
    "pii",
)


@dataclass(frozen=True)
class GuardDecision:
    blocked: bool
    reason: BlockReason | None = None
    labels: tuple[str, ...] = field(default_factory=tuple)
    # Highest malicious score seen across the detectors, in [0, 1].
    score: float = 0.0


class InputGuard(Protocol):
    """Decides whether a question may reach retrieval and the model."""

    def check(self, text: str) -> GuardDecision: ...


def strongest(reasons: set[BlockReason]) -> BlockReason | None:
    for reason in REASON_PRIORITY:
        if reason in reasons:
            return reason
    return None
