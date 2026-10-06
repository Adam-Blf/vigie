from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
import pytest

from vigie.quant.encoder import OnnxEncoder


@dataclass
class FakeEncoding:
    ids: list[int]
    attention_mask: list[int]
    type_ids: list[int]


class FakeTokenizer:
    """One token per word, padded to the longest text of the batch."""

    def encode_batch(self, input: Sequence[Any], /) -> list[FakeEncoding]:
        words = [str(text).split() for text in input]
        width = max(len(w) for w in words)
        return [
            FakeEncoding(
                ids=[len(x) for x in w] + [0] * (width - len(w)),
                attention_mask=[1] * len(w) + [0] * (width - len(w)),
                type_ids=[0] * width,
            )
            for w in words
        ]


@dataclass
class FakeInput:
    name: str


class FakeSession:
    """Token vector = (word length, 1), so the pooled vector is easy to predict."""

    def __init__(self, names: Sequence[str]) -> None:
        self.names = names
        self.feeds: list[dict[str, Any]] = []

    def get_inputs(self) -> list[FakeInput]:
        return [FakeInput(n) for n in self.names]

    def run(self, output_names: Any, input_feed: dict[str, Any]) -> list[Any]:
        self.feeds.append(input_feed)
        ids = input_feed["input_ids"].astype(np.float32)
        return [np.stack([ids, np.ones_like(ids)], axis=-1)]


def test_encode_pools_without_padding_and_normalizes() -> None:
    session = FakeSession(["input_ids", "attention_mask"])
    encoder = OnnxEncoder(session, FakeTokenizer(), batch_size=2)
    vectors = encoder.encode(["abc", "a abcde", "abc"])
    # Row 0 is (3, 1) normalized; padding in the first batch did not dilute it.
    assert vectors[0].tolist() == pytest.approx(vectors[2].tolist())
    assert vectors[0].tolist() == pytest.approx([3 / 10**0.5, 1 / 10**0.5])
    assert np.linalg.norm(vectors, axis=1).tolist() == pytest.approx([1.0, 1.0, 1.0])
    assert len(session.feeds) == 2


def test_token_type_ids_are_fed_only_when_the_graph_declares_them() -> None:
    without = FakeSession(["input_ids", "attention_mask"])
    OnnxEncoder(without, FakeTokenizer()).encode(["a b"])
    assert set(without.feeds[0]) == {"input_ids", "attention_mask"}
    with_types = FakeSession(["input_ids", "attention_mask", "token_type_ids"])
    OnnxEncoder(with_types, FakeTokenizer()).encode(["a b"])
    assert set(with_types.feeds[0]) == {"input_ids", "attention_mask", "token_type_ids"}


def test_tokenize_returns_int64_arrays() -> None:
    encoder = OnnxEncoder(FakeSession(["input_ids"]), FakeTokenizer())
    arrays = encoder.tokenize(["a bb", "ccc"])
    assert arrays["input_ids"].dtype == np.int64
    assert arrays["attention_mask"].tolist() == [[1, 1], [1, 0]]


def test_encoder_rejects_bad_arguments() -> None:
    with pytest.raises(ValueError, match="batch_size"):
        OnnxEncoder(FakeSession(["input_ids"]), FakeTokenizer(), batch_size=0)
    with pytest.raises(ValueError, match="nothing to encode"):
        OnnxEncoder(FakeSession(["input_ids"]), FakeTokenizer()).encode([])
