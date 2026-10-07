"""Detects an answer that recites the system prompt.

The input guard misses part of the extraction attempts (red teaming, J10): encoded or
dressed up as a research request, they look like ordinary questions. Whatever the model
then does, this check reads the answer. Any run of WINDOW consecutive words of the system
prompt found in it counts as a leak, after folding case, accents of the same letter form
and punctuation. The refusal sentence is part of the prompt and is left out, otherwise
every honest refusal would look like a leak.

A paraphrase or a translation of the rules is not caught: this is a tripwire for verbatim
recitation, the common failure of small models, not a semantic judge.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

from vigie.rag.prompt import REFUSAL, SYSTEM_PROMPT

WINDOW = 7
_WORD = re.compile(r"\w+")


def _words(text: str) -> list[str]:
    return _WORD.findall(unicodedata.normalize("NFKC", text).casefold())


def _shingles(words: list[str]) -> set[tuple[str, ...]]:
    return {tuple(words[i : i + WINDOW]) for i in range(len(words) - WINDOW + 1)}


@lru_cache(maxsize=1)
def _reference() -> frozenset[tuple[str, ...]]:
    return frozenset(_shingles(_words(SYSTEM_PROMPT.replace(REFUSAL, " "))))


def prompt_leak(text: str) -> bool:
    return not _reference().isdisjoint(_shingles(_words(text)))
