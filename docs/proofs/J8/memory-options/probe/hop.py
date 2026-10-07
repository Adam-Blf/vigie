"""Cost of one extra local HTTP hop per question, for the shared-model estimate.

    docker exec <api container> python /probe/hop.py remote http://models:8800
    docker exec <models container> python /probe/hop.py local

remote: from the API pod, times GET /healthz (the hop alone, nothing computed) and the two
calls a question makes, POST /embed_query and POST /guard_score. local: the same embedder
and guard loaded in-process, the same texts, no HTTP. The difference per question is the
added latency. 10 warm-up calls, then 100 timed ones; median and p95 in milliseconds.
"""

from __future__ import annotations

import json
import statistics
import sys
import time
import urllib.request
from collections.abc import Callable

TEXTS = [
    "Quelles obligations DORA impose-t-il pour le registre des prestataires tiers ?",
    "Which AI systems are prohibited under the AI Act?",
    "Quel délai pour notifier une violation de données personnelles ?",
    "Qui supervise la lutte contre le blanchiment selon l'AMLR ?",
]


def timed(fn: Callable[[str], object], label: str) -> None:
    for i in range(10):
        fn(TEXTS[i % len(TEXTS)])
    samples = []
    for i in range(100):
        begin = time.perf_counter()
        fn(TEXTS[i % len(TEXTS)])
        samples.append((time.perf_counter() - begin) * 1000)
    samples.sort()
    print(f"{label:34s} median {statistics.median(samples):6.2f} ms   p95 {samples[94]:6.2f} ms")


def main() -> int:
    mode = sys.argv[1]
    if mode == "remote":
        base = sys.argv[2]

        def post(path: str) -> Callable[[str], object]:
            def call(text: str) -> object:
                request = urllib.request.Request(  # noqa: S310 - in-cluster URL
                    f"{base}{path}",
                    data=json.dumps({"text": text}).encode(),
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(request, timeout=30) as r:  # noqa: S310
                    return r.read()

            return call

        def health(_: str) -> object:
            with urllib.request.urlopen(f"{base}/healthz", timeout=30) as r:  # noqa: S310
                return r.read()

        timed(health, "remote GET /healthz (hop only)")
        timed(post("/embed_query"), "remote POST /embed_query")
        timed(post("/guard_score"), "remote POST /guard_score")
        return 0
    from vigie.config import get_settings
    from vigie.guard.classifier import InjectionClassifier
    from vigie.retrieval.embeddings import FastEmbedEmbedder

    settings = get_settings()
    embedder = FastEmbedEmbedder.from_settings(settings)
    classifier = InjectionClassifier.load(
        settings.guard_model_dir, settings.guard_max_tokens, settings.guard_threads
    )
    timed(embedder.embed_query, "in-process embed_query")
    timed(classifier.score, "in-process guard score")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
