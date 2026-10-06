"""Deterministic stand-in for the real model, used by tests, load tests and red teaming.

It reads the passages back from the prompt and answers with the first sentence of each,
followed by the passage label, so every citation it writes is valid. With hallucinate on,
it appends a citation to an article it was never given, which is how the evaluation
proves that the citation filter really removes invented references.
"""

from __future__ import annotations

import re
from collections.abc import Generator, Sequence

from vigie.llm.base import ChatMessage, LLMClient, Usage
from vigie.rag.prompt import REFUSAL, parse_blocks

FAKE_MODEL = "fake-llm"
INVENTED_LABEL = "[DORA art. 999 §9]"
MAX_SENTENCES = 3

_SENTENCE_END = re.compile(r"(?<=[.;:])\s")


def _first_sentence(text: str) -> str:
    sentence = _SENTENCE_END.split(text.strip(), maxsplit=1)[0]
    return sentence.rstrip(" .;:")


def compose_answer(prompt: str, hallucinate: bool) -> str:
    blocks = parse_blocks(prompt)
    if not blocks:
        return REFUSAL
    parts = [f"{_first_sentence(b.text)} {b.label}." for b in blocks[:MAX_SENTENCES]]
    if hallucinate:
        parts.append(f"Une obligation complémentaire s'applique également {INVENTED_LABEL}.")
    return "D'après les textes indexés : " + " ".join(parts)


class FakeLLM(LLMClient):
    def __init__(self, hallucinate: bool = False) -> None:
        self.model = FAKE_MODEL
        self._hallucinate = hallucinate

    def _deltas(self, messages: Sequence[ChatMessage]) -> Generator[str, None, Usage]:
        prompt = "\n".join(m.content for m in messages if m.role == "user")
        answer = compose_answer(prompt, self._hallucinate)
        words = answer.split(" ")
        # Word by word, like a real stream, so streaming code paths are exercised too.
        for index, word in enumerate(words):
            yield word if index == 0 else f" {word}"
        tokens_in = sum(len(m.content.split()) for m in messages)
        return Usage(tokens_in, len(words))
