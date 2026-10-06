import pytest
from k8s_fixtures import deployment, hardened, pod_spec

from vigie.deploy.budget import Budget, compute, pod_resources
from vigie.deploy.manifests import workloads

BUDGET = Budget(requests_mib=1000, limits_mib=1500, cpu_requests_m=500, system_reserve_mib=100)


def test_containers_are_summed_per_pod() -> None:
    spec = pod_spec(hardened("a", "100Mi", "200Mi", "50m"), hardened("b", "50Mi", "100Mi", "1"))
    resources = pod_resources(workloads([deployment("x", spec)])[0])
    assert (resources.request_mib, resources.limit_mib, resources.cpu_request_m) == (150, 300, 1050)


def test_init_container_counts_only_when_it_is_the_peak() -> None:
    small_app = pod_spec(hardened("app", "100Mi", "200Mi"), init=(hardened("i", "400Mi", "500Mi"),))
    big_app = pod_spec(hardened("app", "600Mi", "800Mi"), init=(hardened("i", "400Mi", "500Mi"),))
    assert pod_resources(workloads([deployment("x", small_app)])[0]).request_mib == 400
    assert pod_resources(workloads([deployment("x", big_app)])[0]).request_mib == 600


def test_sidecar_init_container_runs_beside_the_app() -> None:
    sidecar = hardened("proxy", "100Mi", "100Mi") | {"restartPolicy": "Always"}
    spec = pod_spec(hardened("app", "100Mi", "200Mi"), init=(sidecar,))
    assert pod_resources(workloads([deployment("x", spec)])[0]).request_mib == 200


def test_missing_request_falls_back_to_the_limit() -> None:
    container = hardened("app", "1Mi", "300Mi")
    container["resources"] = {"limits": {"memory": "300Mi", "cpu": "200m"}}
    resources = pod_resources(workloads([deployment("x", pod_spec(container))])[0])
    assert (resources.request_mib, resources.cpu_request_m) == (300, 200)


def test_missing_memory_limit_is_an_error() -> None:
    container = hardened("app", "100Mi", "200Mi")
    del container["resources"]["limits"]
    with pytest.raises(ValueError, match="no memory limit"):
        pod_resources(workloads([deployment("x", pod_spec(container))])[0])


def test_missing_cpu_request_is_an_error() -> None:
    container = hardened("app", "100Mi", "200Mi")
    del container["resources"]["requests"]["cpu"]
    with pytest.raises(ValueError, match="no CPU request"):
        pod_resources(workloads([deployment("x", pod_spec(container))])[0])


def test_totals_include_replicas_and_system_reserve() -> None:
    spec = pod_spec(hardened("app", "200Mi", "300Mi", "100m"))
    report = compute(workloads([deployment("x", spec, replicas=3)]), BUDGET)
    assert (report.requests_mib, report.limits_mib, report.cpu_requests_m) == (700, 1000, 300)
    assert report.violations() == []


def test_every_exceeded_dimension_is_reported() -> None:
    spec = pod_spec(hardened("app", "500Mi", "800Mi", "300m"))
    report = compute(workloads([deployment("x", spec, replicas=2)]), BUDGET)
    problems = report.violations()
    assert len(problems) == 3
    assert problems[0] == "memory requests: 1100Mi exceeds the budget of 1000Mi"
