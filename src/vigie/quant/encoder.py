"""Sentence embeddings from an ONNX file: tokenize, run the graph, mean pool, normalize.

The session and the tokenizer are injected, so the pooling and batching logic is tested
with small fakes, and onnxruntime is only imported when a real file is opened.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any, Protocol

import numpy as np
from numpy.typing import NDArray

from vigie.quant.dense import FloatArray, l2_normalize, mean_pool


class Encoding(Protocol):
    @property
    def ids(self) -> list[int]: ...

    @property
    def attention_mask(self) -> list[int]: ...

    @property
    def type_ids(self) -> list[int]: ...


class Tokenizer(Protocol):
    def encode_batch(self, input: Sequence[Any], /) -> Sequence[Encoding]: ...


class Session(Protocol):
    def get_inputs(self) -> Sequence[Any]: ...

    def run(self, output_names: Any, input_feed: dict[str, Any]) -> Sequence[Any]: ...


class OnnxEncoder:
    def __init__(self, session: Session, tokenizer: Tokenizer, batch_size: int = 32) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be at least 1")
        self._session = session
        self._tokenizer = tokenizer
        self._batch_size = batch_size
        self._inputs = {i.name for i in session.get_inputs()}

    @classmethod
    def from_files(cls, model: Path, tokenizer_json: Path, max_tokens: int) -> OnnxEncoder:
        import onnxruntime as ort  # quant extra, imported lazily
        from tokenizers import Tokenizer as HFTokenizer

        tokenizer = HFTokenizer.from_file(str(tokenizer_json))
        tokenizer.enable_truncation(max_length=max_tokens)
        tokenizer.enable_padding()
        options = ort.SessionOptions()
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        session = ort.InferenceSession(
            str(model), sess_options=options, providers=["CPUExecutionProvider"]
        )
        return cls(session, tokenizer)

    def tokenize(self, texts: Sequence[str]) -> dict[str, NDArray[np.int64]]:
        """Padded id, mask and segment arrays for one batch of texts."""
        encodings = self._tokenizer.encode_batch(list(texts))
        return {
            "input_ids": np.asarray([e.ids for e in encodings], dtype=np.int64),
            "attention_mask": np.asarray([e.attention_mask for e in encodings], dtype=np.int64),
            "token_type_ids": np.asarray([e.type_ids for e in encodings], dtype=np.int64),
        }

    def encode(self, texts: Sequence[str]) -> FloatArray:
        """Unit-length vectors, one row per text, in input order."""
        if not texts:
            raise ValueError("nothing to encode")
        rows: list[FloatArray] = []
        for start in range(0, len(texts), self._batch_size):
            arrays = self.tokenize(texts[start : start + self._batch_size])
            # Some exports drop token_type_ids; only feed what the graph declares.
            feed = {name: value for name, value in arrays.items() if name in self._inputs}
            token_embeddings = np.asarray(self._session.run(None, feed)[0], dtype=np.float32)
            rows.append(mean_pool(token_embeddings, arrays["attention_mask"]))
        return l2_normalize(np.concatenate(rows, axis=0))
