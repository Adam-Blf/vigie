"""Measurement hooks for docs/memory-options.md, loaded by Python at startup.

Mounted read-only into the measurement containers and put on PYTHONPATH; never part of
the image. Every switch is an environment variable and does nothing when unset, so the
same mount serves the baseline runs.

    VIGIE_PROBE_ORT_ARENA=0      ONNX Runtime sessions without the CPU memory arena
    VIGIE_PROBE_ORT_PREPACK=0    sessions without weight prepacking
    VIGIE_PROBE_ORT_THREADS=1    intra_op_num_threads forced to this value
    VIGIE_PROBE_ORT_OPT=disable  graph optimisations off (no constant folding at load)
    VIGIE_PROBE_REMOTE_MODELS=http://models:8800
                                 the API pod keeps no model: the embedder and the guard
                                 classifier become HTTP calls to models_service.py
"""

from __future__ import annotations

import os


def _patch_ort() -> None:
    arena = os.environ.get("VIGIE_PROBE_ORT_ARENA")
    prepack = os.environ.get("VIGIE_PROBE_ORT_PREPACK")
    threads = os.environ.get("VIGIE_PROBE_ORT_THREADS")
    opt = os.environ.get("VIGIE_PROBE_ORT_OPT")
    if not (arena or prepack or threads or opt):
        return
    import onnxruntime as ort

    original = ort.InferenceSession

    def session(path_or_bytes, sess_options=None, *args, **kwargs):  # type: ignore[no-untyped-def]
        options = sess_options or ort.SessionOptions()
        if arena == "0":
            options.enable_cpu_mem_arena = False
        if prepack == "0":
            options.add_session_config_entry("session.disable_prepacking", "1")
        if threads:
            options.intra_op_num_threads = int(threads)
        if opt == "disable":
            options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_DISABLE_ALL
        return original(path_or_bytes, options, *args, **kwargs)

    ort.InferenceSession = session  # type: ignore[assignment,misc]


def _patch_remote() -> None:
    base = os.environ.get("VIGIE_PROBE_REMOTE_MODELS")
    if not base:
        return
    import json
    import urllib.request

    import vigie.guard.factory as guard_factory
    import vigie.retrieval.embeddings as embeddings
    from vigie.guard.chain import InputChain

    def call(path: str, payload: dict) -> dict:  # type: ignore[type-arg]
        request = urllib.request.Request(  # noqa: S310 - fixed in-cluster URL
            f"{base}{path}",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
            return json.loads(response.read())  # type: ignore[no-any-return]

    def embedded(raw: dict) -> embeddings.Embedded:  # type: ignore[type-arg]
        sparse = embeddings.SparseVector(tuple(raw["indices"]), tuple(raw["values"]))
        return embeddings.Embedded(tuple(raw["dense"]), sparse)

    class RemoteEmbedder:
        def __init__(self) -> None:
            info = call("/info", {})
            self._id = info["embedding_id"]
            self._size = info["dense_size"]

        @property
        def embedding_id(self) -> str:
            return self._id

        @property
        def dense_size(self) -> int:
            return self._size

        def embed_documents(self, texts):  # type: ignore[no-untyped-def]
            return [embedded(r) for r in call("/embed_documents", {"texts": list(texts)})["items"]]

        def embed_query(self, text):  # type: ignore[no-untyped-def]
            return embedded(call("/embed_query", {"text": text}))

    def remote_guard(settings):  # type: ignore[no-untyped-def]
        def score(text: str) -> float:
            return float(call("/guard_score", {"text": text})["score"])

        return InputChain(scorer=score, threshold=settings.guard_input_threshold)

    embeddings.FastEmbedEmbedder.from_settings = classmethod(  # type: ignore[method-assign]
        lambda cls, settings: RemoteEmbedder()
    )
    guard_factory.build_input_guard = remote_guard  # type: ignore[assignment]


_patch_ort()
_patch_remote()
