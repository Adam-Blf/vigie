"""Export the embedding model to ONNX fp32, then quantize it to int8 with onnxruntime.

Run once on a workstation, never in the API: torch and transformers come from the
``quant`` extra. Weights are read from safetensors at a pinned revision, with remote code
disabled, so the exported graph is exactly the audited checkpoint and nothing else.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

import numpy as np

ONNX_OPSET = 18
TOKENIZER_FILE = "tokenizer.json"


@dataclass(frozen=True)
class ExportedModel:
    fp32: Path
    int8: Path
    tokenizer: Path


def variant_paths(out_dir: Path) -> ExportedModel:
    return ExportedModel(
        fp32=out_dir / "model-fp32.onnx",
        int8=out_dir / "model-int8.onnx",
        tokenizer=out_dir / TOKENIZER_FILE,
    )


def export_fp32(model_id: str, revision: str, out_dir: Path) -> ExportedModel:
    import torch  # quant extra, imported lazily
    from huggingface_hub import hf_hub_download
    from transformers import AutoModel

    paths = variant_paths(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    # Eager attention: the fused SDPA path skips the padding mask when the sample batch has
    # none, and the exported graph then averages padding into every short sentence.
    model = AutoModel.from_pretrained(
        model_id,
        revision=revision,
        use_safetensors=True,
        trust_remote_code=False,
        attn_implementation="eager",
    )
    model.eval()

    # torch is an optional extra: where it is not installed (CI) mypy sees Module as Any.
    class Encoder(torch.nn.Module):  # type: ignore[misc, unused-ignore]
        # Only the token vectors leave the graph; pooling stays in numpy so fp32 and int8
        # share the exact same post-processing.
        def __init__(self) -> None:
            super().__init__()
            self.inner = model

        def forward(
            self,
            input_ids: torch.Tensor,
            attention_mask: torch.Tensor,
            token_type_ids: torch.Tensor,
        ) -> torch.Tensor:
            out = self.inner(
                input_ids=input_ids, attention_mask=attention_mask, token_type_ids=token_type_ids
            )
            hidden: torch.Tensor = out.last_hidden_state
            return hidden

    sample = torch.ones((2, 16), dtype=torch.int64)
    # A padded second row, so the traced graph keeps the mask as a real input.
    mask = sample.clone()
    mask[1, 8:] = 0
    batch, seq = torch.export.Dim("batch"), torch.export.Dim("sequence")
    axes = {0: batch, 1: seq}
    torch.onnx.export(
        Encoder(),
        (sample, mask, torch.zeros_like(sample)),
        str(paths.fp32),
        input_names=["input_ids", "attention_mask", "token_type_ids"],
        output_names=["last_hidden_state"],
        dynamic_shapes={"input_ids": axes, "attention_mask": axes, "token_type_ids": axes},
        opset_version=ONNX_OPSET,
        dynamo=True,
        external_data=False,
        verbose=False,
    )
    tokenizer = hf_hub_download(model_id, TOKENIZER_FILE, revision=revision)
    shutil.copyfile(tokenizer, paths.tokenizer)
    return paths


def quantize_int8(paths: ExportedModel) -> Path:
    from onnxruntime.quantization import QuantType, quantize_dynamic

    # Dynamic quantization: int8 weights, activations quantized on the fly per batch. No
    # calibration set is needed, which keeps the dev questions out of the model itself.
    quantize_dynamic(str(paths.fp32), str(paths.int8), weight_type=QuantType.QInt8)
    return paths.int8


def parity_gap(model_id: str, revision: str, paths: ExportedModel, texts: list[str]) -> float:
    """Largest gap between the ONNX fp32 sentence vectors and the PyTorch ones.

    A broken export can still produce plausible vectors, so the fp32 graph is checked
    against the original model on a padded batch before any figure is trusted.
    """
    import torch  # quant extra, imported lazily
    from transformers import AutoModel

    from vigie.quant.dense import l2_normalize, mean_pool
    from vigie.quant.encoder import OnnxEncoder

    encoder = OnnxEncoder.from_files(paths.fp32, paths.tokenizer, max_tokens=128)
    onnx_vectors = encoder.encode(texts)
    model = AutoModel.from_pretrained(
        model_id, revision=revision, use_safetensors=True, trust_remote_code=False
    )
    model.eval()
    batch = encoder.tokenize(texts)
    ids = torch.tensor(batch["input_ids"])
    mask = torch.tensor(batch["attention_mask"])
    with torch.no_grad():
        hidden = model(input_ids=ids, attention_mask=mask).last_hidden_state.numpy()
    reference = l2_normalize(mean_pool(hidden, batch["attention_mask"]))
    return float(np.max(np.abs(onnx_vectors - reference)))
