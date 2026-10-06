"""The ProtectAI DeBERTa injection classifier, run by ONNX Runtime from its int8 export.

No torch and no transformers here: the tokenizer is the Rust "tokenizers" library and
the model is a plain ONNX graph, which is what lets the API image stay small (section
11.7 of the brief). The files come from python -m vigie.guard.prepare.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from vigie.guard.prepare import CONFIG_FILE, MODEL_FILE, TOKENIZER_FILE

INJECTION_LABEL = "INJECTION"


class Session(Protocol):
    def get_inputs(self) -> list[Any]: ...

    def run(self, output_names: Any, input_feed: dict[str, Any]) -> list[Any]: ...


class Encoding(Protocol):
    ids: list[int]
    attention_mask: list[int]


class Tokenizer(Protocol):
    def encode(self, text: str, /) -> Encoding: ...


class ModelMissingError(FileNotFoundError):
    """The classifier files are absent; run python -m vigie.guard.prepare first."""


def injection_index(config_path: Path) -> int:
    id2label = json.loads(config_path.read_text(encoding="utf-8"))["id2label"]
    for index, label in id2label.items():
        if label == INJECTION_LABEL:
            return int(index)
    raise ValueError(f"{config_path} has no {INJECTION_LABEL} label")


def softmax(logits: np.ndarray[Any, Any]) -> np.ndarray[Any, Any]:
    shifted = np.exp(logits - logits.max())
    result: np.ndarray[Any, Any] = shifted / shifted.sum()
    return result


class InjectionClassifier:
    def __init__(self, session: Session, tokenizer: Tokenizer, injection_index: int) -> None:
        self._session = session
        self._tokenizer = tokenizer
        self._index = injection_index
        self._inputs = {item.name for item in session.get_inputs()}

    @classmethod
    def load(cls, model_dir: Path, max_tokens: int, threads: int) -> InjectionClassifier:
        paths = [model_dir / name for name in (MODEL_FILE, TOKENIZER_FILE, CONFIG_FILE)]
        missing = [p.name for p in paths if not p.exists()]
        if missing:
            raise ModelMissingError(
                f"guard model files missing in {model_dir}: {', '.join(missing)}; "
                "run python -m vigie.guard.prepare"
            )
        # Heavy imports stay here, so the regex-only chain and the tests never pay them.
        import onnxruntime as ort
        from tokenizers import Tokenizer as HFTokenizer

        options = ort.SessionOptions()
        options.intra_op_num_threads = threads
        options.inter_op_num_threads = 1
        session = ort.InferenceSession(
            str(paths[0]), sess_options=options, providers=["CPUExecutionProvider"]
        )
        # Typed loosely: the library stubs describe a wider encode() than the one used here.
        tokenizer: Any = HFTokenizer.from_file(str(paths[1]))
        tokenizer.enable_truncation(max_length=max_tokens)
        tokenizer.no_padding()
        return cls(session, tokenizer, injection_index(paths[2]))

    def score(self, text: str) -> float:
        """Probability that the text is a prompt injection, in [0, 1]."""
        encoding = self._tokenizer.encode(text)
        feed = {
            "input_ids": np.array([encoding.ids], dtype=np.int64),
            "attention_mask": np.array([encoding.attention_mask], dtype=np.int64),
        }
        logits = self._session.run(None, {k: v for k, v in feed.items() if k in self._inputs})[0]
        return float(softmax(np.asarray(logits[0], dtype=np.float64))[self._index])
