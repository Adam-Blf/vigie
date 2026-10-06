from typing import Any

import pytest
from k8s_fixtures import deployment, hardened, pod_spec

from vigie.deploy.manifests import load_documents, workloads


def _rollout(steps: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "kind": "Rollout",
        "metadata": {"name": "vigie-api", "namespace": "vigie"},
        "spec": {
            "replicas": 1,
            "strategy": {"canary": {"steps": steps}},
            "template": {"spec": pod_spec(hardened("api", "512Mi", "704Mi"))},
        },
    }


def _hpa(kind: str, name: str, ceiling: int) -> dict[str, Any]:
    return {
        "kind": "HorizontalPodAutoscaler",
        "spec": {"scaleTargetRef": {"kind": kind, "name": name}, "maxReplicas": ceiling},
    }


def test_load_documents_skips_empty_documents() -> None:
    text = "---\nkind: ConfigMap\n---\n\n---\nkind: Service\n"
    assert [doc["kind"] for doc in load_documents(text)] == ["ConfigMap", "Service"]


def test_non_workloads_are_ignored() -> None:
    assert workloads([{"kind": "Service", "metadata": {"name": "web"}}]) == []


def test_deployment_counts_its_replicas() -> None:
    (found,) = workloads([deployment("web", pod_spec(hardened("web", "32Mi", "64Mi")), 2)])
    assert (found.kind, found.name, found.namespace, found.pods) == (
        "Deployment",
        "web",
        "vigie",
        2,
    )


def test_rollout_counts_hpa_ceiling_plus_canary_scale() -> None:
    docs = [_rollout([{"setCanaryScale": {"replicas": 1}}, {"setWeight": 10}])]
    docs.append(_hpa("Rollout", "vigie-api", 3))
    (found,) = workloads(docs)
    assert found.pods == 4


def test_rollout_without_canary_scale_assumes_full_surge() -> None:
    (found,) = workloads([_rollout([{"setWeight": 10}]), _hpa("Rollout", "vigie-api", 3)])
    assert found.pods == 6


def test_rollout_without_steps_adds_nothing() -> None:
    doc = _rollout([])
    doc["spec"]["strategy"] = {}
    (found,) = workloads([doc])
    assert found.pods == 1


def test_jobs_and_cronjobs_use_parallelism() -> None:
    spec = pod_spec(hardened("job", "64Mi", "128Mi"))
    job = {"kind": "Job", "metadata": {"name": "ingest"}, "spec": {"template": {"spec": spec}}}
    cron = {
        "kind": "CronJob",
        "metadata": {"name": "snap"},
        "spec": {"jobTemplate": {"spec": {"parallelism": 2, "template": {"spec": spec}}}},
    }
    found = workloads([job, cron])
    assert [(w.kind, w.pods, w.namespace) for w in found] == [
        ("Job", 1, "default"),
        ("CronJob", 2, "default"),
    ]


def test_bare_pod_is_one_pod() -> None:
    pod = {"kind": "Pod", "metadata": {"name": "debug"}, "spec": pod_spec()}
    assert workloads([pod])[0].pods == 1


def test_workload_without_pod_spec_is_an_error() -> None:
    with pytest.raises(ValueError, match="no pod spec"):
        workloads([{"kind": "Deployment", "metadata": {"name": "broken"}, "spec": {}}])
