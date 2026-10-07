"""ONNX Runtime session settings that trade a little speed for resident memory.

The API pod holds two ONNX models, the dense embedder and the injection classifier, in a
950 MiB budget (docs/architecture.md). By default ONNX Runtime keeps a second, prepacked
copy of quantized weights and a growing CPU arena for activations; both are memory the pod
pays for good. VIGIE_ONNX_LOW_MEMORY turns them off for both sessions. The numbers stay the
same, only the layout of the weights in memory changes.
"""

from __future__ import annotations

from typing import Any


def apply_low_memory(options: Any) -> None:
    """Set an onnxruntime.SessionOptions to drop prepacked weights and the CPU arena."""
    options.enable_cpu_mem_arena = False
    options.add_session_config_entry("session.disable_prepacking", "1")
