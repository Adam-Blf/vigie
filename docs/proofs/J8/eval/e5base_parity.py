"""Parity and size of the per-channel int8 export of multilingual-e5-base.

Run from the repository root, after `vigie-quant export` with VIGIE_DENSE_MODEL and
VIGIE_DENSE_MODEL_REVISION set to e5-base:
PYTHONPATH=src python docs/proofs/J8/eval/e5base_parity.py
Prints the largest gap between PyTorch sentence vectors and those of the fp32 graph (the
export check of the J12 study, tolerance 1e-4) and of the int8 graph, then the file sizes.
"""

from pathlib import Path

import numpy as np
import torch
from transformers import AutoModel

from vigie.quant.cli import PARITY_TEXTS
from vigie.quant.dense import l2_normalize, mean_pool
from vigie.quant.encoder import OnnxEncoder
from vigie.quant.export import variant_paths

MODEL = "intfloat/multilingual-e5-base"
REVISION = "d128750597153bb5987e10b1c3493a34e5a4502a"
paths = variant_paths(Path("data/quant/intfloat-multilingual-e5-base"))
texts = ["query: " + PARITY_TEXTS[0], "passage: " + PARITY_TEXTS[1]]

reference_model = AutoModel.from_pretrained(
    MODEL, revision=REVISION, use_safetensors=True, trust_remote_code=False
)
reference_model.eval()
for name, path in (("fp32", paths.fp32), ("int8", paths.int8)):
    encoder = OnnxEncoder.from_files(path, paths.tokenizer, max_tokens=512)
    batch = encoder.tokenize(texts)
    with torch.no_grad():
        hidden = reference_model(
            input_ids=torch.tensor(batch["input_ids"]),
            attention_mask=torch.tensor(batch["attention_mask"]),
        ).last_hidden_state.numpy()
    reference = l2_normalize(mean_pool(hidden, batch["attention_mask"]))
    vectors = encoder.encode(texts)
    gap = float(np.max(np.abs(vectors - reference)))
    cosine = float(np.min(np.sum(vectors * reference, axis=1)))
    print(f"{name}: max abs gap {gap:.3e}, lowest cosine to PyTorch {cosine:.6f}")
fp32_size, int8_size = paths.fp32.stat().st_size, paths.int8.stat().st_size
print(
    f"fp32 file {fp32_size} bytes, int8 file {int8_size} bytes, ratio {int8_size / fp32_size:.3f}"
)
