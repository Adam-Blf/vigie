"""The dense model as the ONNX int8 file of the J12 study, instead of fastembed's copy.

J12 exported the embedding model to ONNX and quantized it with onnxruntime; int8 kept the
recall and divided the file by four, so it is the deployed variant (docs/quantization.md).
This adapter gives that file the two methods the hybrid embedder calls on a fastembed
model, so the index and the search do not care which one they talk to.

Files live in one folder per model, `<quant_dir>/<model slug>/`, as `vigie-quant export
--models` writes them: two exports of different models can never be mixed up.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator, Sequence
from pathlib import Path
from typing import Protocol

import numpy as np

from vigie.quant.export import variant_paths


class _Encoder(Protocol):
    def encode(self, texts: Sequence[str]) -> np.ndarray: ...


class OnnxModelMissingError(RuntimeError):
    """The int8 variant is asked for but its files were never exported."""


def model_slug(model: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", model.lower()).strip("-")


def model_dir(quant_dir: Path, model: str) -> Path:
    return quant_dir / model_slug(model)


class OnnxDense:
    """Batches documents through the encoder, one call per query."""

    def __init__(self, encoder: _Encoder, size: int) -> None:
        self._encoder = encoder
        self._size = size

    @property
    def embedding_size(self) -> int:
        return self._size

    def embed(self, documents: Iterable[str]) -> Iterator[np.ndarray]:
        texts = list(documents)
        if not texts:
            return iter(())
        return iter(self._encoder.encode(texts))

    def query_embed(self, query: str) -> Iterator[np.ndarray]:
        return iter(self._encoder.encode([query]))


def load_int8(model: str, quant_dir: Path, max_tokens: int) -> OnnxDense:
    from vigie.quant.encoder import OnnxEncoder

    paths = variant_paths(model_dir(quant_dir, model))
    if not paths.int8.exists() or not paths.tokenizer.exists():
        raise OnnxModelMissingError(
            f"no int8 export of {model} in {paths.int8.parent}; run "
            f"vigie-quant export --models {paths.int8.parent}, or set VIGIE_DENSE_VARIANT=fp32"
        )
    encoder = OnnxEncoder.from_files(paths.int8, paths.tokenizer, max_tokens)
    # The width is read from one encoded word rather than written down per model.
    size = int(encoder.encode(["dimension"]).shape[1])
    return OnnxDense(encoder, size)
