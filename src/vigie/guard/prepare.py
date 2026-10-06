"""Fetch the injection classifier and quantize it to int8, once, at build time.

    python -m vigie.guard.prepare            write models/guard/ (VIGIE_GUARD_MODEL_DIR)

ProtectAI publishes an ONNX export of the classifier next to its weights, so torch is
never needed: the file is downloaded at a pinned revision, quantized with ONNX Runtime's
dynamic int8 quantization, and written with its tokenizer and a manifest of hashes. The
API image runs this step at build time and reads the result offline.

Needs the "guard-model" extra (huggingface-hub and onnx); the API itself does not.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, TextIO

from vigie.config import Settings, get_settings

MODEL_FILE = "model.int8.onnx"
TOKENIZER_FILE = "tokenizer.json"
CONFIG_FILE = "config.json"
MANIFEST_FILE = "manifest.json"
_REMOTE = {"model": "onnx/model.onnx", "tokenizer": "onnx/tokenizer.json", "config": "config.json"}

Download = Callable[[str, str, str], str]
Quantize = Callable[[Path, Path], None]


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def hub_download(repo: str, filename: str, revision: str) -> str:
    from huggingface_hub import hf_hub_download

    path: str = hf_hub_download(repo_id=repo, filename=filename, revision=revision)
    return path


def int8_quantize(source: Path, target: Path) -> None:
    from onnxruntime.quantization import QuantType, quantize_dynamic

    quantize_dynamic(source, target, weight_type=QuantType.QInt8, per_channel=True)


def prepare(
    settings: Settings,
    download: Download = hub_download,
    quantize: Quantize = int8_quantize,
) -> dict[str, Any]:
    out = settings.guard_model_dir
    out.mkdir(parents=True, exist_ok=True)
    repo, revision = settings.guard_model_repo, settings.guard_model_revision
    fetched = {key: Path(download(repo, name, revision)) for key, name in _REMOTE.items()}
    quantize(fetched["model"], out / MODEL_FILE)
    shutil.copyfile(fetched["tokenizer"], out / TOKENIZER_FILE)
    shutil.copyfile(fetched["config"], out / CONFIG_FILE)
    manifest: dict[str, Any] = {
        "repo": repo,
        "revision": revision,
        "source_onnx_sha256": sha256_of(fetched["model"]),
        "source_onnx_bytes": fetched["model"].stat().st_size,
        "quantization": "onnxruntime dynamic, weights QInt8 per channel",
        "files": {
            name: {"sha256": sha256_of(out / name), "bytes": (out / name).stat().st_size}
            for name in (MODEL_FILE, TOKENIZER_FILE, CONFIG_FILE)
        },
    }
    (out / MANIFEST_FILE).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main(argv: Sequence[str] | None = None, out: TextIO = sys.stdout) -> int:
    del argv  # no options: everything comes from the settings, pinned revision included
    manifest = prepare(get_settings())
    out.write(json.dumps(manifest, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
