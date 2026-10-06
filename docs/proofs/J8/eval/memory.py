"""Resident memory of the dense model alone, as the API pod would hold it.

Run from the repository root, one model per process so nothing is shared between them:
PYTHONPATH=src python docs/proofs/J8/eval/memory.py int8 intfloat/multilingual-e5-base 512
PYTHONPATH=src python docs/proofs/J8/eval/memory.py fp32 intfloat/multilingual-e5-large 512
Prints the RSS before loading, after loading, and after encoding one 512-token passage
and one question. The int8 files come from vigie-quant export, the fp32 ones from fastembed.
"""

import sys
from pathlib import Path

import psutil

from vigie.retrieval.models import profile_for, register_custom_model
from vigie.retrieval.onnx_dense import load_int8

variant, model, max_tokens = sys.argv[1], sys.argv[2], int(sys.argv[3])
process = psutil.Process()


def rss() -> float:
    return process.memory_info().rss / 2**20


before = rss()
profile = profile_for(model)
if variant == "int8":
    dense = load_int8(model, Path("data/quant"), max_tokens)
    embed_doc, embed_query = dense.embed, dense.query_embed
else:
    from fastembed import TextEmbedding

    register_custom_model(model)
    fast = TextEmbedding(model_name=model, cache_dir="data/cache/models")
    embed_doc, embed_query = fast.embed, fast.query_embed
loaded = rss()
passage = profile.passage_prefix + "L'entité financière gère le risque lié aux tiers. " * 60
list(embed_doc([passage]))
list(embed_query(profile.query_prefix + "Quel registre une banque tient-elle ?"))
used = rss()
print(
    f"{variant} {model}: before {before:.0f} MiB, loaded {loaded:.0f} MiB, "
    f"after one passage and one query {used:.0f} MiB, model share {used - before:.0f} MiB"
)
