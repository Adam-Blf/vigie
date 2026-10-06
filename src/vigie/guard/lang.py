"""A two-way language guess, French or English, for routing a question to the classifier.

The benchmark showed DeBERTa flags most French questions as injections with a score above
0.99, so no threshold can rescue it there; in English it is reliable. The chain therefore
sends English text to the model and leaves French to the regex, which was written for
it. A dictionary of function words is enough to tell the two apart on a question, costs
microseconds, and needs no model of its own.
"""

from __future__ import annotations

import re
from typing import Literal

Language = Literal["fr", "en"]

_WORD = re.compile(r"[a-zàâäçéèêëîïôöùûüÿœ']+")

_FRENCH = frozenset(
    [
        "le",
        "la",
        "les",
        "un",
        "une",
        "des",
        "du",
        "de",
        "au",
        "aux",
        "et",
        "est",
        "sont",
        "pour",
        "que",
        "qui",
        "quoi",
        "dans",
        "sur",
        "par",
        "pas",
        "avec",
        "ce",
        "cette",
        "ces",
        "mon",
        "ma",
        "mes",
        "ton",
        "ta",
        "tes",
        "son",
        "sa",
        "ses",
        "nous",
        "vous",
        "ils",
        "elles",
        "je",
        "tu",
        "il",
        "elle",
        "quel",
        "quelle",
        "quels",
        "quelles",
        "comment",
        "selon",
        "doit",
        "doivent",
        "peut",
        "entre",
        "leur",
        "leurs",
        "ou",
        "où",
        "ne",
        "plus",
        "tout",
        "tous",
        "toutes",
        "être",
        "avoir",
        "fait",
        "faire",
    ]
)
_ENGLISH = frozenset(
    [
        "the",
        "a",
        "an",
        "and",
        "is",
        "are",
        "for",
        "that",
        "which",
        "who",
        "what",
        "in",
        "on",
        "by",
        "not",
        "with",
        "this",
        "these",
        "my",
        "your",
        "his",
        "her",
        "its",
        "our",
        "their",
        "we",
        "you",
        "they",
        "i",
        "he",
        "she",
        "how",
        "under",
        "must",
        "can",
        "should",
        "between",
        "or",
        "do",
        "does",
        "did",
        "be",
        "been",
        "have",
        "has",
        "all",
        "any",
        "from",
        "of",
        "to",
        "it",
    ]
)
_ACCENTS = frozenset("àâäçéèêëîïôöùûüÿœ")


def guess_language(text: str) -> Language:
    words = _WORD.findall(text.lower())
    french = sum(w in _FRENCH or w.startswith(("l'", "d'", "qu'", "n'", "s'")) for w in words)
    english = sum(w in _ENGLISH for w in words)
    # Accents weigh as one French word each, capped so a single "é" in an English
    # sentence quoting a French name does not flip it.
    french += min(3, sum(ch in _ACCENTS for ch in text.lower()))
    return "en" if english > french else "fr"
