"""Sum the memory and CPU a set of workloads can claim on the node.

The arithmetic follows the scheduler: a pod reserves the larger of its regular
containers summed and its biggest init container, and a request left empty takes the
value of the limit. Each workload is then multiplied by its worst-case pod count, so an
autoscaled API counts at its ceiling plus the canary pod.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from vigie.deploy.manifests import Workload
from vigie.deploy.quantity import MIB, cpu_millicores, memory_bytes


@dataclass(frozen=True)
class PodResources:
    request_mib: int
    limit_mib: int
    cpu_request_m: int


@dataclass(frozen=True)
class Line:
    workload: Workload
    pod: PodResources

    @property
    def request_mib(self) -> int:
        return self.pod.request_mib * self.workload.pods

    @property
    def limit_mib(self) -> int:
        return self.pod.limit_mib * self.workload.pods

    @property
    def cpu_request_m(self) -> int:
        return self.pod.cpu_request_m * self.workload.pods


@dataclass(frozen=True)
class Budget:
    requests_mib: int
    limits_mib: int
    cpu_requests_m: int
    system_reserve_mib: int


@dataclass
class Report:
    budget: Budget
    lines: list[Line] = field(default_factory=list)

    @property
    def requests_mib(self) -> int:
        return self.budget.system_reserve_mib + sum(line.request_mib for line in self.lines)

    @property
    def limits_mib(self) -> int:
        return self.budget.system_reserve_mib + sum(line.limit_mib for line in self.lines)

    @property
    def cpu_requests_m(self) -> int:
        return sum(line.cpu_request_m for line in self.lines)

    def violations(self) -> list[str]:
        checks = (
            ("memory requests", self.requests_mib, self.budget.requests_mib, "Mi"),
            ("memory limits", self.limits_mib, self.budget.limits_mib, "Mi"),
            ("CPU requests", self.cpu_requests_m, self.budget.cpu_requests_m, "m"),
        )
        return [
            f"{label}: {used}{unit} exceeds the budget of {allowed}{unit}"
            for label, used, allowed, unit in checks
            if used > allowed
        ]


def _container(container: Mapping[str, Any], owner: str) -> PodResources:
    resources = container.get("resources") or {}
    limits = resources.get("limits") or {}
    requests = resources.get("requests") or {}
    name = f"{owner}/{container.get('name')}"
    if "memory" not in limits:
        raise ValueError(f"{name} has no memory limit")
    limit = memory_bytes(limits["memory"])
    request = memory_bytes(requests.get("memory", limits["memory"]))
    cpu = requests.get("cpu", limits.get("cpu"))
    if cpu is None:
        raise ValueError(f"{name} has no CPU request")
    return PodResources(-(-request // MIB), -(-limit // MIB), cpu_millicores(cpu))


def _add(a: PodResources, b: PodResources) -> PodResources:
    return PodResources(
        a.request_mib + b.request_mib, a.limit_mib + b.limit_mib, a.cpu_request_m + b.cpu_request_m
    )


def _peak(a: PodResources, b: PodResources) -> PodResources:
    return PodResources(
        max(a.request_mib, b.request_mib),
        max(a.limit_mib, b.limit_mib),
        max(a.cpu_request_m, b.cpu_request_m),
    )


def pod_resources(workload: Workload) -> PodResources:
    owner = f"{workload.kind}/{workload.name}"
    running = PodResources(0, 0, 0)
    init_peak = PodResources(0, 0, 0)
    for init in workload.pod_spec.get("initContainers") or []:
        # A restartable init container is a sidecar: it keeps running beside the app.
        if init.get("restartPolicy") == "Always":
            running = _add(running, _container(init, owner))
        else:
            init_peak = _peak(init_peak, _container(init, owner))
    for container in workload.pod_spec.get("containers") or []:
        running = _add(running, _container(container, owner))
    return _peak(running, init_peak)


def compute(workloads: Iterable[Workload], budget: Budget) -> Report:
    report = Report(budget)
    for workload in workloads:
        report.lines.append(Line(workload, pod_resources(workload)))
    return report
