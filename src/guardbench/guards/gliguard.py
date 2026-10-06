"""GLiGuard (fastino, 300M encoder) through the gliner2 library.

One encoder pass scores both the binary safety task and the attack-strategy task, so
asking for both costs no extra latency.
"""

from __future__ import annotations

from typing import Any

from guardbench.guards.base import Guard, GuardUnavailableError, Verdict

SAFETY_LABELS = ["safe", "unsafe"]
JAILBREAK_LABELS = [
    "prompt_injection",
    "jailbreak_attempt",
    "policy_evasion",
    "instruction_override",
    "system_prompt_exfiltration",
    "data_exfiltration",
    "roleplay_bypass",
    "hypothetical_bypass",
    "obfuscated_attack",
    "multi_step_attack",
    "social_engineering",
    "benign",
]
# Threshold published on the model card for the multi-label task.
_JAILBREAK_TASK = {"labels": JAILBREAK_LABELS, "multi_label": True, "cls_threshold": 0.4}


def _as_pairs(value: Any) -> list[tuple[str, float]]:
    """Flatten whatever shape gliner2 returns into (label, confidence) pairs."""
    if value is None:
        return []
    if isinstance(value, str):
        return [(value, 1.0)]
    if isinstance(value, dict):
        return [(str(value.get("label", "")), float(value.get("confidence", 1.0)))]
    pairs: list[tuple[str, float]] = []
    for item in value:
        pairs.extend(_as_pairs(item))
    return pairs


def parse_result(result: dict[str, Any]) -> Verdict:
    safety = _as_pairs(result.get("prompt_safety"))
    attacks = [
        (lab, conf)
        for lab, conf in _as_pairs(result.get("jailbreak_detection"))
        if lab and lab != "benign"
    ]
    unsafe = [conf for lab, conf in safety if lab == "unsafe"]
    labels = tuple(sorted({lab for lab, _ in attacks} | ({"unsafe"} if unsafe else set())))
    score = max([*unsafe, *(conf for _, conf in attacks), 0.0])
    return Verdict(flagged=bool(labels), labels=labels, score=score)


class GliGuard(Guard):
    name = "gliguard"
    covers = frozenset(
        {
            "direct_injection",
            "indirect_injection",
            "jailbreak",
            "system_prompt_leak",
            "unsafe_content",
            "pii",
        }
    )

    def __init__(self, model_id: str, threshold: float) -> None:
        self.model_id = model_id
        self.threshold = threshold
        self._model: Any = None

    def setup(self) -> None:
        try:
            from gliner2 import GLiNER2
        except ImportError as exc:
            raise GuardUnavailableError("gliner2[local] is not installed") from exc
        self._model = GLiNER2.from_pretrained(self.model_id)

    def check(self, text: str) -> Verdict:
        result = self._model.classify_text(
            text,
            {"prompt_safety": SAFETY_LABELS, "jailbreak_detection": _JAILBREAK_TASK},
            threshold=self.threshold,
            include_confidence=True,
        )
        return parse_result(result)
