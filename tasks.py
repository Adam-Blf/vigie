"""Project task runner. Plain Python so it works the same on Windows and Linux, no .bat or .ps1.

Usage: python tasks.py <task> [args...]
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TASKS: dict[str, Callable[[Sequence[str]], int]] = {}


def task(fn: Callable[[Sequence[str]], int]) -> Callable[[Sequence[str]], int]:
    TASKS[fn.__name__.replace("_", "-")] = fn
    return fn


def run(cmd: Sequence[str]) -> int:
    print("+", " ".join(cmd), flush=True)
    return subprocess.call(list(cmd), cwd=ROOT)  # noqa: S603 - commands are fixed lists


def py(*args: str) -> list[str]:
    return [sys.executable, "-m", *args]


@task
def lint(_: Sequence[str]) -> int:
    return run(py("ruff", "check", ".")) or run(py("ruff", "format", "--check", "."))


@task
def typecheck(_: Sequence[str]) -> int:
    return run(py("mypy", "src"))


@task
def test(args: Sequence[str]) -> int:
    return run(py("pytest", "--cov=src", "--cov-report=term-missing", *args))


@task
def check(args: Sequence[str]) -> int:
    for step in (lint, typecheck, test):
        code = step(args if step is test else [])
        if code:
            return code
    return 0


# Kubernetes API version of k3s v1.35 (deploy/versions.env), for the core schemas.
K8S_SCHEMA_VERSION = "1.35.0"
K8S_LAYERS = ("overlays/dev", "overlays/prod", "overlays/prod-loadtest", "system", "cd")
CRDS_CATALOG = (
    "https://raw.githubusercontent.com/datreeio/CRDs-catalog/"
    "d373c2da9702bc9509a004db83e57263fe3bdfc1/{{.Group}}/{{.ResourceKind}}_{{.ResourceAPIVersion}}.json"
)


@task
def k8s_validate(args: Sequence[str]) -> int:
    """Render every kustomize layer, validate it, then check the node budget.

    Needs kustomize and kubeconform on PATH. Usage: k8s-validate [output dir].
    """
    out = Path(args[0]) if args else ROOT / "build" / "k8s"
    out.mkdir(parents=True, exist_ok=True)
    rendered = {}
    for layer in K8S_LAYERS:
        target = out / (layer.replace("/", "-") + ".yaml")
        print("+ kustomize build", layer, ">", target, flush=True)
        build = subprocess.run(  # noqa: S603 - fixed command, layer from a constant
            ["kustomize", "build", str(ROOT / "deploy" / "k8s" / layer)],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
        )
        if build.returncode:
            print(build.stderr)
            return build.returncode
        target.write_text(build.stdout, encoding="utf-8")
        rendered[layer] = str(target)
    schemas = ["-schema-location", "default", "-schema-location", CRDS_CATALOG]
    # CustomResourceDefinitions come verbatim from the pinned Argo Rollouts and Flux
    # releases and no schema catalog covers the CRD kind itself; the resources built on
    # them (Rollout, ImagePolicy, IngressRoute...) are validated against the catalog.
    validate = [
        "kubeconform",
        "-strict",
        "-summary",
        "-output",
        "text",
        "-kubernetes-version",
        K8S_SCHEMA_VERSION,
        "-skip",
        "CustomResourceDefinition",
        *schemas,
    ]
    return run([*validate, *rendered.values()]) or run(
        py("vigie.deploy", rendered["overlays/prod"], rendered["system"])
    )


def main(argv: Sequence[str]) -> int:
    if not argv or argv[0] not in TASKS:
        print("tasks:", ", ".join(sorted(TASKS)))
        return 2
    return TASKS[argv[0]](argv[1:])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
