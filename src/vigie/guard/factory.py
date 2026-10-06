"""Builds the input chain from the settings.

With the classifier switched on (the default), a missing model is a startup error, not a
silent fallback to the regex: an API that quietly lost half its guard would look healthy
while letting paraphrased attacks through.
"""

from __future__ import annotations

from vigie.config import Settings
from vigie.guard.chain import InputChain
from vigie.guard.classifier import InjectionClassifier


def build_input_guard(settings: Settings) -> InputChain:
    if settings.guard_classifier == "off":
        return InputChain()
    classifier = InjectionClassifier.load(
        settings.guard_model_dir, settings.guard_max_tokens, settings.guard_threads
    )
    return InputChain(scorer=classifier.score, threshold=settings.guard_input_threshold)
