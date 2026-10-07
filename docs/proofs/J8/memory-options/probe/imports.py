"""Resident cost of each heavy import of the API, each in a fresh interpreter.

    docker exec <api container> python /probe/imports.py

Tells which imports a lazy import could defer: only a module the request path never uses
can be left unloaded, the others are paid at the first question anyway.
"""

import subprocess
import sys

MODULES = [
    "numpy",
    "pydantic",
    "fastapi",
    "uvicorn",
    "httpx",
    "qdrant_client",
    "onnxruntime",
    "tokenizers",
    "fastembed",
    "vigie.config",
    "vigie.guard.chain",
    "vigie.retrieval.search",
    "vigie.api.app",
    "vigie.api.__main__",
]
HEAVY = "onnxruntime fastembed qdrant_client grpc numpy pandas scipy sklearn mlflow tokenizers"
PROBE = f"""
import importlib, sys
def rss():
    for line in open('/proc/self/status'):
        if line.startswith('VmRSS'):
            return int(line.split()[1]) // 1024
base = rss()
importlib.import_module(sys.argv[1])
pulled = ' '.join(m for m in '{HEAVY}'.split() if m in sys.modules)
print(f'{{sys.argv[1]:22s}} +{{rss() - base:4d}} MiB   pulls: {{pulled}}')
"""
for module in MODULES:
    out = subprocess.run(  # noqa: S603 - this interpreter, fixed code
        [sys.executable, "-c", PROBE, module], capture_output=True, text=True, check=False
    )
    print(out.stdout.strip() or f"{module:22s} failed: {out.stderr.strip().splitlines()[-1]}")
