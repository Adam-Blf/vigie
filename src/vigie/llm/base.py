"""Common contract for every LLM provider.

Providers only implement one generator that yields text deltas and returns the token
usage at the end. Both the blocking call and the streaming call are derived from it, so a
provider cannot stream one answer and return a different one when called in one go.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Generator, Iterator, Sequence
from dataclasses import dataclass
from typing import Literal

Role = Literal["system", "user", "assistant"]

# Error kinds double as the `kind` label of vigie_llm_errors_total, keep the set small.
LLMErrorKind = Literal["timeout", "unavailable", "overloaded", "http", "model", "disabled"]


@dataclass(frozen=True)
class ChatMessage:
    role: Role
    content: str


@dataclass(frozen=True)
class Usage:
    tokens_in: int
    tokens_out: int


@dataclass(frozen=True)
class LLMResult:
    text: str
    tokens_in: int
    tokens_out: int


class LLMError(RuntimeError):
    """Raised by providers so the API can map a failure to a status code and a metric."""

    def __init__(self, kind: LLMErrorKind, message: str) -> None:
        super().__init__(message)
        self.kind: LLMErrorKind = kind


class LLMStream:
    """Iterates over text deltas, then exposes the complete result once exhausted."""

    def __init__(self, deltas: Generator[str, None, Usage]) -> None:
        self._deltas = deltas
        self._parts: list[str] = []
        self._result: LLMResult | None = None

    def __iter__(self) -> Iterator[str]:
        # Drive the generator by hand: a plain for loop would swallow the Usage it returns.
        while True:
            try:
                delta = next(self._deltas)
            except StopIteration as stop:
                usage: Usage = stop.value
                self._result = LLMResult("".join(self._parts), usage.tokens_in, usage.tokens_out)
                return
            if delta:
                self._parts.append(delta)
                yield delta

    @property
    def result(self) -> LLMResult:
        if self._result is None:
            raise RuntimeError("the stream must be fully consumed before reading its result")
        return self._result


class LLMClient(ABC):
    """A chat model. `model` is the exact tag reported in answers and metrics."""

    model: str

    @abstractmethod
    def _deltas(self, messages: Sequence[ChatMessage]) -> Generator[str, None, Usage]:
        """Yield the answer piece by piece and return the token usage."""

    def stream(self, messages: Sequence[ChatMessage]) -> LLMStream:
        return LLMStream(self._deltas(messages))

    def generate(self, messages: Sequence[ChatMessage]) -> LLMResult:
        stream = self.stream(messages)
        for _ in stream:
            pass
        return stream.result
