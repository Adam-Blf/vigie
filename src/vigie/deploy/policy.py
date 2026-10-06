"""Hardening rules every pod of the project must follow (brief 11.10).

Pod Security `restricted` already refuses some of these at admission time, but only on
the cluster. Checking the rendered manifests catches the same mistakes in CI, and adds
the two rules admission does not enforce: a read-only root filesystem and no service
account token mounted by default.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from vigie.deploy.manifests import Workload


def _container_problems(container: Mapping[str, Any], pod_ctx: Mapping[str, Any]) -> list[str]:
    ctx = container.get("securityContext") or {}
    name = container.get("name")
    problems = []
    if not (ctx.get("runAsNonRoot") or pod_ctx.get("runAsNonRoot")):
        problems.append(f"container {name}: runAsNonRoot is not set")
    if ctx.get("readOnlyRootFilesystem") is not True:
        problems.append(f"container {name}: root filesystem is writable")
    if ctx.get("allowPrivilegeEscalation") is not False:
        problems.append(f"container {name}: privilege escalation is allowed")
    if "ALL" not in ((ctx.get("capabilities") or {}).get("drop") or []):
        problems.append(f"container {name}: capabilities are not all dropped")
    seccomp = (ctx.get("seccompProfile") or pod_ctx.get("seccompProfile") or {}).get("type")
    if seccomp != "RuntimeDefault":
        problems.append(f"container {name}: seccomp profile is not RuntimeDefault")
    return problems


def problems(workload: Workload) -> list[str]:
    """Every hardening rule the workload breaks, prefixed with its name."""
    spec = workload.pod_spec
    found = []
    if spec.get("automountServiceAccountToken") is not False:
        found.append("service account token is mounted automatically")
    if spec.get("hostNetwork") or spec.get("hostPID") or spec.get("hostIPC"):
        found.append("pod shares a host namespace")
    pod_ctx = spec.get("securityContext") or {}
    containers = [*(spec.get("initContainers") or []), *(spec.get("containers") or [])]
    for container in containers:
        found.extend(_container_problems(container, pod_ctx))
    return [f"{workload.kind}/{workload.name}: {issue}" for issue in found]


def check_all(workloads: Iterable[Workload]) -> list[str]:
    return [issue for workload in workloads for issue in problems(workload)]


def _floating(image: str) -> bool:
    """True when the reference does not name one precise build."""
    if "@sha256:" in image:
        return False
    tag = image.rsplit("/", 1)[-1].partition(":")[2]
    return tag in ("", "latest")


def image_problems(workloads: Iterable[Workload]) -> list[str]:
    """Images without a tag or digest, or on `latest`, in a rendered overlay.

    The base leaves the project images untagged on purpose, so this check only makes
    sense on the output of an overlay, where every image must point at one build.
    """
    found = []
    for workload in workloads:
        spec = workload.pod_spec
        for container in [*(spec.get("initContainers") or []), *(spec.get("containers") or [])]:
            image = str(container.get("image", ""))
            if _floating(image):
                found.append(f"{workload.kind}/{workload.name}: floating image {image!r}")
    return found
