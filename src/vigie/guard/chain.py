"""The production input chain, as recommended by docs/guardrails-benchmark.md.

First the reference regex of the benchmark: under a millisecond, no false positive on
the test split, and the only detector that understands French attacks here. Then, for
English text the regex let through, the DeBERTa classifier in ONNX int8, which catches
the paraphrased injections the rules miss. The regex is reused from src/guardbench as
is, so production runs exactly the detector that was measured.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from guardbench.guards.regex import find_labels
from vigie.guard.base import BlockReason, GuardDecision, strongest
from vigie.guard.lang import Language, guess_language

# Regex labels of the benchmark, mapped to the reasons the interface explains.
LABEL_REASONS: dict[str, BlockReason] = {
    "instruction_override": "injection",
    "role_reassignment": "injection",
    "indirect_marker": "injection",
    "jailbreak": "jailbreak",
    "system_prompt_leak": "prompt_leak",
    "tool_abuse": "other",
    "pii_email": "pii",
    "pii_iban": "pii",
    "pii_phone": "pii",
    "pii_card": "pii",
}
CLASSIFIER_LABEL = "classifier_injection"

Scorer = Callable[[str], float]


@dataclass
class InputChain:
    # Probability of injection from the classifier, or None for a regex-only chain.
    scorer: Scorer | None = None
    threshold: float = 0.5
    languages: frozenset[Language] = frozenset({"en"})

    def check(self, text: str) -> GuardDecision:
        labels = find_labels(text)
        if labels:
            reasons = {LABEL_REASONS.get(label, "other") for label in labels}
            return GuardDecision(True, strongest(reasons), labels, 1.0)
        if self.scorer is None or guess_language(text) not in self.languages:
            return GuardDecision(False)
        score = self.scorer(text)
        if score >= self.threshold:
            return GuardDecision(True, "injection", (CLASSIFIER_LABEL,), score)
        return GuardDecision(False, score=score)
