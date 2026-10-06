"""ProtectAI DeBERTa v3 prompt-injection classifier (v2) through transformers.

It only answers "injection or not". It was trained mostly on English, which is exactly
why it has to be measured on French before anyone trusts it here.
"""

from __future__ import annotations

from typing import Any

from guardbench.guards.base import Guard, GuardUnavailableError, Verdict

INJECTION_LABEL = "INJECTION"


def injection_score(prediction: dict[str, Any]) -> float:
    """Probability of the INJECTION class, whichever label the pipeline put on top."""
    score = float(prediction["score"])
    return score if prediction["label"] == INJECTION_LABEL else 1.0 - score


class DebertaGuard(Guard):
    name = "deberta"
    covers = frozenset({"direct_injection", "indirect_injection", "jailbreak"})

    def __init__(self, model_id: str, threshold: float) -> None:
        self.model_id = model_id
        self.threshold = threshold
        self._pipe: Any = None

    def setup(self) -> None:
        try:
            from transformers import pipeline
        except ImportError as exc:
            raise GuardUnavailableError("transformers is not installed") from exc
        self._pipe = pipeline(
            "text-classification",
            model=self.model_id,
            truncation=True,
            max_length=512,
            device="cpu",
        )

    def check(self, text: str) -> Verdict:
        score = injection_score(self._pipe(text)[0])
        flagged = score >= self.threshold
        return Verdict(flagged=flagged, labels=(INJECTION_LABEL,) if flagged else (), score=score)
