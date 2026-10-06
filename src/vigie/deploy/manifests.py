"""Turn a multi-document YAML stream into the workloads it will run.

A workload is anything that ends up as pods: Deployment, StatefulSet, Rollout, Job,
CronJob and friends. For each one we keep its pod spec and the number of pods it can run
at its worst, which is what the node has to absorb.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

import yaml

Manifest = Mapping[str, Any]

_TEMPLATE_KINDS = {"Deployment", "StatefulSet", "ReplicaSet", "DaemonSet", "Rollout"}
_JOB_KINDS = {"Job", "CronJob"}


@dataclass(frozen=True)
class Workload:
    kind: str
    name: str
    namespace: str
    pod_spec: Manifest
    pods: int


def load_documents(text: str) -> list[Manifest]:
    """Parse every non-empty document of a YAML stream."""
    return [doc for doc in yaml.safe_load_all(text) if isinstance(doc, Mapping)]


def _get(node: Any, *path: str) -> Any:
    for key in path:
        if not isinstance(node, Mapping):
            return None
        node = node.get(key)
    return node


def _hpa_ceilings(docs: Iterable[Manifest]) -> dict[tuple[str, str], int]:
    ceilings: dict[tuple[str, str], int] = {}
    for doc in docs:
        if doc.get("kind") != "HorizontalPodAutoscaler":
            continue
        target = _get(doc, "spec", "scaleTargetRef") or {}
        ceilings[(str(target.get("kind")), str(target.get("name")))] = int(
            _get(doc, "spec", "maxReplicas") or 1
        )
    return ceilings


def _canary_extra(doc: Manifest, replicas: int) -> int:
    """Pods a canary adds on top of the stable ones while it runs.

    An explicit `setCanaryScale` caps it. Without one, Argo Rollouts may bring the
    canary up to the full replica count, so we assume the worst.
    """
    steps = _get(doc, "spec", "strategy", "canary", "steps")
    if not isinstance(steps, list):
        return 0
    scales = [
        int(_get(step, "setCanaryScale", "replicas"))
        for step in steps
        if _get(step, "setCanaryScale", "replicas") is not None
    ]
    return max(scales) if scales else replicas


def _workload(doc: Manifest, ceilings: Mapping[tuple[str, str], int]) -> Workload | None:
    kind = str(doc.get("kind"))
    name = str(_get(doc, "metadata", "name"))
    namespace = str(_get(doc, "metadata", "namespace") or "default")
    if kind in _TEMPLATE_KINDS:
        spec = _get(doc, "spec", "template", "spec")
        replicas = ceilings.get((kind, name), int(_get(doc, "spec", "replicas") or 1))
        if kind == "Rollout":
            replicas += _canary_extra(doc, replicas)
    elif kind in _JOB_KINDS:
        job = _get(doc, "spec", "jobTemplate", "spec") if kind == "CronJob" else doc.get("spec")
        spec = _get(job, "template", "spec")
        replicas = int(_get(job, "parallelism") or 1)
    elif kind == "Pod":
        spec, replicas = doc.get("spec"), 1
    else:
        return None
    if not isinstance(spec, Mapping):
        raise ValueError(f"{kind}/{name} has no pod spec")
    return Workload(kind, name, namespace, spec, replicas)


def workloads(docs: Iterable[Manifest]) -> list[Workload]:
    """Every workload of the stream, with its worst-case pod count."""
    docs = list(docs)
    ceilings = _hpa_ceilings(docs)
    found = (_workload(doc, ceilings) for doc in docs)
    return [w for w in found if w is not None]
