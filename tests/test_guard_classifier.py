"""The classifier and its preparation, with ONNX Runtime and the hub replaced by stand-ins:
the real 244 MB model is measured by python -m vigie.guard.measure, not in CI."""

import io
import json
import sys
import types
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from vigie.config import Settings
from vigie.guard import prepare
from vigie.guard.classifier import InjectionClassifier, injection_index, softmax


class Input:
    def __init__(self, name: str) -> None:
        self.name = name


class FakeSession:
    def __init__(self, logits: list[float], names: tuple[str, ...] = ("input_ids",)) -> None:
        self.logits = logits
        self.names = names
        self.feeds: list[dict[str, Any]] = []

    def get_inputs(self) -> list[Input]:
        return [Input(n) for n in self.names]

    def run(self, output_names: Any, input_feed: dict[str, Any]) -> list[Any]:
        self.feeds.append(input_feed)
        return [np.array([self.logits])]


class FakeEncoding:
    ids = [1, 42, 2]
    attention_mask = [1, 1, 1]


class FakeTokenizer:
    def __init__(self) -> None:
        self.truncation: int | None = None

    def encode(self, text: str) -> FakeEncoding:
        return FakeEncoding()

    def enable_truncation(self, max_length: int) -> None:
        self.truncation = max_length

    def no_padding(self) -> None:
        pass


def write_config(directory: Path, id2label: dict[str, str]) -> Path:
    path = directory / prepare.CONFIG_FILE
    path.write_text(json.dumps({"id2label": id2label}), encoding="utf-8")
    return path


def test_score_is_the_softmax_of_the_injection_logit() -> None:
    session = FakeSession([0.0, 2.0])
    classifier = InjectionClassifier(session, FakeTokenizer(), injection_index=1)
    assert classifier.score("x") == pytest.approx(float(softmax(np.array([0.0, 2.0]))[1]))
    # Only the inputs the graph declares are fed to it.
    assert set(session.feeds[0]) == {"input_ids"}
    assert session.feeds[0]["input_ids"].dtype == np.int64


def test_injection_index_reads_the_label_map(tmp_path: Path) -> None:
    assert injection_index(write_config(tmp_path, {"0": "SAFE", "1": "INJECTION"})) == 1
    with pytest.raises(ValueError, match="INJECTION"):
        injection_index(write_config(tmp_path, {"0": "NEG", "1": "POS"}))


def test_load_wires_runtime_tokenizer_and_threads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in (prepare.MODEL_FILE, prepare.TOKENIZER_FILE):
        (tmp_path / name).write_bytes(b"stub")
    write_config(tmp_path, {"0": "SAFE", "1": "INJECTION"})
    built: dict[str, Any] = {}
    tokenizer = FakeTokenizer()

    class Options:
        intra_op_num_threads = 0
        inter_op_num_threads = 0

    def session(path: str, sess_options: Options, providers: list[str]) -> FakeSession:
        built.update(path=path, threads=sess_options.intra_op_num_threads, providers=providers)
        return FakeSession([3.0, -3.0], ("input_ids", "attention_mask"))

    ort = types.SimpleNamespace(SessionOptions=Options, InferenceSession=session)
    tok = types.SimpleNamespace(Tokenizer=types.SimpleNamespace(from_file=lambda p: tokenizer))
    monkeypatch.setitem(sys.modules, "onnxruntime", ort)
    monkeypatch.setitem(sys.modules, "tokenizers", tok)

    classifier = InjectionClassifier.load(tmp_path, max_tokens=256, threads=2)
    assert built["path"].endswith(prepare.MODEL_FILE) and built["threads"] == 2
    assert built["providers"] == ["CPUExecutionProvider"]
    assert tokenizer.truncation == 256
    assert classifier.score("safe question") < 0.01


def fake_hub(tmp_path: Path) -> tuple[prepare.Download, list[tuple[str, str, str]]]:
    calls: list[tuple[str, str, str]] = []
    source = tmp_path / "hub"
    source.mkdir()

    def download(repo: str, filename: str, revision: str) -> str:
        calls.append((repo, filename, revision))
        path = source / filename.replace("/", "_")
        if filename.endswith("config.json"):
            path.write_text('{"id2label": {"0": "SAFE", "1": "INJECTION"}}', encoding="utf-8")
        else:
            path.write_bytes(filename.encode())
        return str(path)

    return download, calls


def test_prepare_downloads_pinned_files_quantizes_and_writes_a_manifest(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, guard_model_dir=tmp_path / "out")
    download, calls = fake_hub(tmp_path)

    def quantize(source: Path, target: Path) -> None:
        target.write_bytes(b"int8:" + source.read_bytes())

    manifest = prepare.prepare(settings, download=download, quantize=quantize)
    assert {c[2] for c in calls} == {settings.guard_model_revision}
    assert {c[1] for c in calls} == {"onnx/model.onnx", "onnx/tokenizer.json", "config.json"}
    out = tmp_path / "out"
    assert (out / prepare.MODEL_FILE).read_bytes() == b"int8:onnx/model.onnx"
    written = json.loads((out / prepare.MANIFEST_FILE).read_text(encoding="utf-8"))
    assert written == manifest
    assert manifest["files"][prepare.MODEL_FILE]["sha256"] == prepare.sha256_of(
        out / prepare.MODEL_FILE
    )


def test_hub_download_and_quantize_call_their_libraries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: dict[str, Any] = {}
    hub = types.SimpleNamespace(hf_hub_download=lambda **kw: seen.setdefault("hub", kw) and "p")
    quant = types.SimpleNamespace(
        QuantType=types.SimpleNamespace(QInt8="QInt8"),
        quantize_dynamic=lambda s, t, **kw: seen.update(quant=(s, t, kw)),
    )
    monkeypatch.setitem(sys.modules, "huggingface_hub", hub)
    monkeypatch.setitem(sys.modules, "onnxruntime.quantization", quant)
    assert prepare.hub_download("org/model", "onnx/model.onnx", "abc") == "p"
    assert seen["hub"] == {"repo_id": "org/model", "filename": "onnx/model.onnx", "revision": "abc"}
    prepare.int8_quantize(tmp_path / "a", tmp_path / "b")
    assert seen["quant"][2] == {"weight_type": "QInt8", "per_channel": True}


def test_prepare_main_prints_the_manifest(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(prepare, "prepare", lambda settings: {"revision": "abc"})
    out = io.StringIO()
    assert prepare.main([], out=out) == 0
    assert json.loads(out.getvalue()) == {"revision": "abc"}
