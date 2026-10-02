"""The committed manifests themselves, read without kustomize so CI needs no binary."""

from pathlib import Path
from typing import Any

import yaml

from vigie.config import Settings
from vigie.deploy.budget import Budget, compute
from vigie.deploy.manifests import load_documents, workloads
from vigie.deploy.policy import check_all

K8S = Path(__file__).resolve().parents[2] / "deploy" / "k8s"
BASE = K8S / "base"


def _base_docs() -> list[dict[str, object]]:
    docs = []
    for path in sorted(BASE.glob("*.yaml")):
        if path.name != "kustomization.yaml":
            docs.extend(load_documents(path.read_text(encoding="utf-8")))
    return docs


def _only(kind: str) -> Any:
    matches = [doc for doc in _base_docs() if doc["kind"] == kind]
    assert len(matches) == 1, kind
    return matches[0]


def _env(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return dict(line.split("=", 1) for line in lines if line and not line.startswith("#"))


def test_every_base_pod_is_hardened() -> None:
    found = workloads(_base_docs())
    assert {w.name for w in found} >= {"vigie-api", "qdrant", "mlflow", "prometheus", "ollama"}
    assert check_all(found) == []


def test_base_alone_fits_the_node_budget() -> None:
    settings = Settings(_env_file=None)
    budget = Budget(
        settings.k8s_requests_budget_mib,
        settings.k8s_limits_budget_mib,
        settings.k8s_cpu_requests_budget_m,
        settings.k8s_system_reserve_mib,
    )
    assert compute(workloads(_base_docs()), budget).violations() == []


def test_namespace_enforces_restricted_pod_security() -> None:
    namespace = _only("Namespace")
    labels = namespace["metadata"]["labels"]
    assert labels["pod-security.kubernetes.io/enforce"] == "restricted"


def test_champion_bundle_never_injects_faults() -> None:
    # Fault injection exists for the canary rollback demo only (brief 11.9). The bundle
    # deployed by default must not carry it, and no overlay may switch it on.
    assert float(_env(BASE / "config" / "bundle.env")["VIGIE_FAULT_ERROR_RATE"]) == 0.0
    for kustomization in K8S.glob("overlays/*/kustomization.yaml"):
        text = kustomization.read_text(encoding="utf-8")
        assert "FAULT_ERROR_RATE" not in text, kustomization


def test_metadata_endpoint_is_excluded_from_every_internet_egress() -> None:
    docs = load_documents((BASE / "network-policies.yaml").read_text(encoding="utf-8"))
    blocks = [
        peer["ipBlock"]
        for doc in docs
        for rule in doc["spec"].get("egress", [])
        for peer in rule.get("to", [])
        if "ipBlock" in peer
    ]
    assert blocks, "expected at least one internet egress rule"
    for block in blocks:
        assert "169.254.169.254/32" in block["except"]


def test_default_deny_covers_both_directions() -> None:
    docs = load_documents((BASE / "network-policies.yaml").read_text(encoding="utf-8"))
    deny = next(d for d in docs if d["metadata"]["name"] == "default-deny")
    assert deny["spec"] == {"podSelector": {}, "policyTypes": ["Ingress", "Egress"]}


def test_canary_steps_match_the_brief() -> None:
    rollout = _only("Rollout")
    steps = rollout["spec"]["strategy"]["canary"]["steps"]
    shape = [next(iter(step)) for step in steps]
    assert shape == [
        "setCanaryScale",
        "setWeight",
        "pause",
        "analysis",
        "setWeight",
        "pause",
        "analysis",
        "setWeight",
    ]
    assert [s["setWeight"] for s in steps if "setWeight" in s] == [10, 50, 100]
    assert {s["pause"]["duration"] for s in steps if "pause" in s} == {"45s"}


def test_analysis_never_passes_on_an_empty_series() -> None:
    template = _only("AnalysisTemplate")
    for metric in template["spec"]["metrics"]:
        assert metric["successCondition"].startswith("len(result) > 0 &&")
        assert metric["failureCondition"].startswith("len(result) > 0 &&")
        assert (metric["initialDelay"], metric["interval"], metric["count"]) == ("30s", "15s", 4)
        assert (metric["failureLimit"], metric["inconclusiveLimit"]) == (1, 2)


def test_yaml_files_parse() -> None:
    for path in K8S.rglob("*.yaml"):
        list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
