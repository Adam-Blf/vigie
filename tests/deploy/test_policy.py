from k8s_fixtures import deployment, hardened, pod_spec

from vigie.deploy.manifests import workloads
from vigie.deploy.policy import check_all


def _issues(spec: dict[str, object]) -> list[str]:
    return check_all(workloads([deployment("web", spec)]))


def test_hardened_pod_passes() -> None:
    assert _issues(pod_spec(hardened("web", "32Mi", "64Mi"))) == []


def test_service_account_token_must_not_be_mounted() -> None:
    spec = pod_spec(hardened("web", "32Mi", "64Mi"))
    del spec["automountServiceAccountToken"]
    assert _issues(spec) == ["Deployment/web: service account token is mounted automatically"]


def test_host_namespaces_are_refused() -> None:
    spec = pod_spec(hardened("web", "32Mi", "64Mi")) | {"hostNetwork": True}
    assert _issues(spec) == ["Deployment/web: pod shares a host namespace"]


def test_each_missing_container_field_is_named() -> None:
    weak = {"name": "web", "resources": {}, "securityContext": {}}
    spec = pod_spec(weak)
    spec["securityContext"] = {}
    issues = _issues(spec)
    assert issues == [
        "Deployment/web: container web: runAsNonRoot is not set",
        "Deployment/web: container web: root filesystem is writable",
        "Deployment/web: container web: privilege escalation is allowed",
        "Deployment/web: container web: capabilities are not all dropped",
        "Deployment/web: container web: seccomp profile is not RuntimeDefault",
    ]


def test_init_containers_are_checked_too() -> None:
    weak_init = hardened("init", "32Mi", "64Mi")
    weak_init["securityContext"]["readOnlyRootFilesystem"] = False
    spec = pod_spec(hardened("web", "32Mi", "64Mi"), init=(weak_init,))
    assert _issues(spec) == ["Deployment/web: container init: root filesystem is writable"]


def test_container_level_context_is_enough() -> None:
    container = hardened("web", "32Mi", "64Mi")
    container["securityContext"] |= {
        "runAsNonRoot": True,
        "seccompProfile": {"type": "RuntimeDefault"},
    }
    spec = pod_spec(container)
    spec["securityContext"] = {}
    assert _issues(spec) == []
