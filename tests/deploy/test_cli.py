import io
import runpy
from pathlib import Path

import pytest
import yaml
from k8s_fixtures import deployment, hardened, pod_spec

from vigie.config import get_settings
from vigie.deploy.cli import main


@pytest.fixture(autouse=True)
def _small_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIGIE_K8S_REQUESTS_BUDGET_MIB", "1000")
    monkeypatch.setenv("VIGIE_K8S_LIMITS_BUDGET_MIB", "1500")
    monkeypatch.setenv("VIGIE_K8S_SYSTEM_RESERVE_MIB", "100")
    monkeypatch.setenv("VIGIE_K8S_CPU_REQUESTS_BUDGET_M", "500")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _write(tmp_path: Path, name: str, *docs: dict[str, object]) -> str:
    path = tmp_path / name
    path.write_text(yaml.safe_dump_all(docs), encoding="utf-8")
    return str(path)


def _app(request: str, image: str = "ghcr.io/adam-blf/vigie-web:dev") -> dict[str, object]:
    return deployment("web", pod_spec(hardened("web", request, "600Mi") | {"image": image}))


def test_fitting_hardened_manifests_pass(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main([_write(tmp_path, "ok.yaml", _app("200Mi"))]) == 0
    out = capsys.readouterr().out
    assert "vigie/Deployment/web" in out
    assert out.rstrip().endswith("OK")


def test_over_budget_fails(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main([_write(tmp_path, "big.yaml", _app("950Mi"))]) == 1
    assert "FAIL memory requests: 1050Mi exceeds the budget of 1000Mi" in capsys.readouterr().out


def test_floating_image_fails(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = _write(tmp_path, "latest.yaml", _app("200Mi", "ghcr.io/adam-blf/vigie-web:latest"))
    assert main([source]) == 1
    assert "floating image" in capsys.readouterr().out


def test_policy_only_applies_to_the_project_namespace(tmp_path: Path) -> None:
    addon = _app("100Mi")
    addon["metadata"] = {"name": "controller", "namespace": "argo-rollouts"}
    addon["spec"]["template"]["spec"]["automountServiceAccountToken"] = True  # type: ignore[index]
    assert main([_write(tmp_path, "addon.yaml", addon)]) == 0


def test_module_entry_point_exits_with_the_verdict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sys.argv", ["vigie.deploy", _write(tmp_path, "big.yaml", _app("950Mi"))])
    with pytest.raises(SystemExit) as exit_info:
        runpy.run_module("vigie.deploy", run_name="__main__")
    assert exit_info.value.code == 1


def test_reads_stdin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(yaml.safe_dump(_app("200Mi"))))
    assert main(["-"]) == 0
