import pytest
from k8s_fixtures import deployment, hardened, pod_spec

from vigie.deploy.manifests import workloads
from vigie.deploy.policy import image_problems


def _with_image(image: str) -> list[str]:
    container = hardened("app", "32Mi", "64Mi") | {"image": image}
    return image_problems(workloads([deployment("app", pod_spec(container))]))


@pytest.mark.parametrize(
    "image",
    [
        "ghcr.io/adam-blf/vigie-api:main-abc1234-1700000000",
        "localhost:5000/vigie-api:dev",
        "docker.io/qdrant/qdrant:v1.19.1@sha256:" + "0" * 64,
        "quay.io/argoproj/argo-rollouts@sha256:" + "1" * 64,
    ],
)
def test_pinned_images_pass(image: str) -> None:
    assert _with_image(image) == []


@pytest.mark.parametrize(
    "image", ["ghcr.io/adam-blf/vigie-api", "ghcr.io/adam-blf/vigie-web:latest", "localhost:5000/x"]
)
def test_floating_images_are_reported(image: str) -> None:
    assert _with_image(image) == [f"Deployment/app: floating image {image!r}"]
