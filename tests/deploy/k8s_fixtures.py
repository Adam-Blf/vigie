"""Small builders for synthetic manifests, shared by the deploy tests."""

from typing import Any

Container = dict[str, Any]


def hardened(name: str, request: str, limit: str, cpu: str = "100m") -> Container:
    return {
        "name": name,
        "resources": {"requests": {"memory": request, "cpu": cpu}, "limits": {"memory": limit}},
        "securityContext": {
            "allowPrivilegeEscalation": False,
            "readOnlyRootFilesystem": True,
            "capabilities": {"drop": ["ALL"]},
        },
    }


def pod_spec(*containers: Container, init: tuple[Container, ...] = ()) -> dict[str, Any]:
    spec: dict[str, Any] = {
        "automountServiceAccountToken": False,
        "securityContext": {"runAsNonRoot": True, "seccompProfile": {"type": "RuntimeDefault"}},
        "containers": list(containers),
    }
    if init:
        spec["initContainers"] = list(init)
    return spec


def deployment(name: str, spec: dict[str, Any], replicas: int = 1) -> dict[str, Any]:
    return {
        "kind": "Deployment",
        "metadata": {"name": name, "namespace": "vigie"},
        "spec": {"replicas": replicas, "template": {"spec": spec}},
    }
