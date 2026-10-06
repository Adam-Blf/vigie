"""deploy/versions.env and the manifests must name the same builds."""

from pathlib import Path

DEPLOY = Path(__file__).resolve().parents[2] / "deploy"


def _versions() -> dict[str, str]:
    lines = (DEPLOY / "versions.env").read_text(encoding="utf-8").splitlines()
    pairs = (line.split("=", 1) for line in lines if line and not line.startswith("#"))
    return {key: value for key, value in pairs}


def _manifests() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in (DEPLOY / "k8s").rglob("*.yaml"))


def test_every_pinned_application_image_is_the_one_deployed() -> None:
    manifests = _manifests()
    for key in ("QDRANT_IMAGE", "MLFLOW_IMAGE", "PROMETHEUS_IMAGE", "OLLAMA_IMAGE", "CURL_IMAGE"):
        assert _versions()[key] in manifests, key


def test_images_are_pinned_by_digest() -> None:
    for key, value in _versions().items():
        if key.endswith("_IMAGE"):
            assert "@sha256:" in value, key


def test_add_on_versions_match_the_install_urls() -> None:
    versions = _versions()
    system = DEPLOY / "k8s" / "system"
    argo = (system / "argo-rollouts" / "kustomization.yaml").read_text(encoding="utf-8")
    flux = (system / "flux" / "kustomization.yaml").read_text(encoding="utf-8")
    assert f"/download/{versions['ARGO_ROLLOUTS_VERSION']}/install.yaml" in argo
    assert versions["ARGO_ROLLOUTS_IMAGE"].split("@")[1] in argo
    assert f"/download/{versions['FLUX_VERSION']}/install.yaml" in flux
