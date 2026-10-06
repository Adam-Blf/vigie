"""Microsoft Presidio analyzer, French and English, limited to banking identifiers.

Presidio is a PII detector, not an injection detector, so its in-scope score is the
one that matters. Out of the box its pattern recognizers only speak English; the French
copies are registered by hand, with the French phone region, so a French question gets
the same treatment as its translation.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from guardbench.guards.base import Guard, GuardUnavailableError, Verdict

LANGUAGES = ("fr", "en")
_SPACY_MODELS = {"fr": "fr_core_news_sm", "en": "en_core_web_sm"}


class PresidioGuard(Guard):
    name = "presidio"
    covers = frozenset({"pii"})

    def __init__(self, entities: Sequence[str], threshold: float) -> None:
        self.entities = list(entities)
        self.threshold = threshold
        self._engine: Any = None

    def setup(self) -> None:
        try:
            from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
            from presidio_analyzer.nlp_engine import NlpEngineProvider
            from presidio_analyzer.predefined_recognizers import (
                CreditCardRecognizer,
                EmailRecognizer,
                IbanRecognizer,
                PhoneRecognizer,
            )
        except ImportError as exc:
            raise GuardUnavailableError("presidio-analyzer is not installed") from exc
        provider = NlpEngineProvider(
            nlp_configuration={
                "nlp_engine_name": "spacy",
                "models": [
                    {"lang_code": lang, "model_name": model}
                    for lang, model in _SPACY_MODELS.items()
                ],
            }
        )
        try:
            nlp_engine = provider.create_engine()
        except OSError as exc:
            raise GuardUnavailableError(f"spaCy models missing: {exc}") from exc
        registry = RecognizerRegistry(supported_languages=list(LANGUAGES))
        for lang in LANGUAGES:
            registry.add_recognizer(EmailRecognizer(supported_language=lang))
            registry.add_recognizer(IbanRecognizer(supported_language=lang))
            registry.add_recognizer(CreditCardRecognizer(supported_language=lang))
            registry.add_recognizer(
                PhoneRecognizer(supported_regions=("FR", "GB", "US"), supported_language=lang)
            )
        self._engine = AnalyzerEngine(
            nlp_engine=nlp_engine, registry=registry, supported_languages=list(LANGUAGES)
        )

    def check(self, text: str) -> Verdict:
        found: dict[str, float] = {}
        for lang in LANGUAGES:
            for hit in self._engine.analyze(text=text, entities=self.entities, language=lang):
                if hit.score >= self.threshold:
                    found[hit.entity_type] = max(found.get(hit.entity_type, 0.0), hit.score)
        return Verdict(
            flagged=bool(found),
            labels=tuple(sorted(found)),
            score=max(found.values(), default=0.0),
        )
