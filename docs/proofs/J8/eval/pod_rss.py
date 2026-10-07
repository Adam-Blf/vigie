"""Resident memory of one API process, as a pod would run it, with a given dense model.

Starts `python -m vigie.api` with the caller's VIGIE_* settings (dense model, variant,
window, Qdrant path, guard model folder), the fake LLM and a throwaway token database,
sends questions through POST /v1/ask so the guard, the dense and BM25 models and the
fusion all run, then reads the memory of the server process. Run from the repository root:
PYTHONPATH=src python docs/proofs/J8/eval/pod_rss.py
Prints the resident set after start, after the questions, and the peak. Qdrant is embedded
here (VIGIE_QDRANT_PATH), so the figure also holds the collection the cluster keeps in its
own Qdrant pod: it errs on the high side.
"""

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
import psutil

from vigie.api.auth import TokenStore

QUESTIONS = [
    "Quelles obligations DORA impose-t-il pour le registre des prestataires tiers ?",
    "Which AI systems are prohibited under the AI Act?",
    "Quel délai pour notifier une violation de données personnelles ?",
    "Qui supervise la lutte contre le blanchiment selon l'AMLR ?",
    "What must a financial entity test in its digital operational resilience programme?",
] * 4
PORT = "8799"


def mib(value: int) -> float:
    return value / 2**20


def tree(root: psutil.Process) -> list[psutil.Process]:
    # On Windows the venv python.exe is a launcher that starts the real interpreter as a
    # child: the server is the whole tree, not the first process.
    return [root, *root.children(recursive=True)]


def rss(root: psutil.Process) -> tuple[int, int]:
    infos = [process.memory_info() for process in tree(root)]
    return sum(i.rss for i in infos), sum(getattr(i, "peak_wset", i.rss) for i in infos)


with tempfile.TemporaryDirectory() as tmp:
    db = Path(tmp) / "rss.sqlite3"
    token = TokenStore(db, ttl_days=1).create("rss-probe").secret
    env = dict(
        os.environ,
        VIGIE_DB_PATH=str(db),
        VIGIE_AUDIT_DIR=str(Path(tmp) / "audit"),
        VIGIE_LLM_PROVIDER="fake",
        VIGIE_PORT=PORT,
    )
    server = subprocess.Popen(  # noqa: S603 - fixed argv, this interpreter, no shell
        [sys.executable, "-m", "vigie.api"],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        base = f"http://127.0.0.1:{PORT}"
        for _ in range(240):
            try:
                if httpx.get(f"{base}/healthz", timeout=2).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(1)
        process = psutil.Process(server.pid)
        started, _ = rss(process)
        statuses = []
        for question in QUESTIONS:
            response = httpx.post(
                f"{base}/v1/ask",
                json={"question": question},
                headers={"Authorization": f"Bearer {token}"},
                timeout=120,
            )
            statuses.append(response.status_code)
        after, peak = rss(process)
        model = os.environ.get("VIGIE_DENSE_MODEL", "default")
        variant = os.environ.get("VIGIE_DENSE_VARIANT", "int8")
        print(f"{model} {variant}: statuses {sorted(set(statuses))} over {len(statuses)} asks")
        print(
            f"rss after start {mib(started):.0f} MiB, after asks {mib(after):.0f} MiB, "
            f"peak {mib(peak):.0f} MiB"
        )
    finally:
        server.terminate()
        server.wait(timeout=30)
