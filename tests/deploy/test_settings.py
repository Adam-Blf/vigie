import pytest

from vigie.config import Settings


def test_node_budget_defaults_follow_the_brief() -> None:
    settings = Settings(_env_file=None)
    # 8.5 GiB of requests, 10.5 GiB of limits, 1.2 GiB for k3s, on a 12 GB node.
    assert settings.k8s_requests_budget_mib == 8704
    assert settings.k8s_limits_budget_mib == 10752
    assert settings.k8s_system_reserve_mib == 1229
    assert settings.k8s_cpu_requests_budget_m == 1800


def test_node_budget_is_configurable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIGIE_K8S_LIMITS_BUDGET_MIB", "4096")
    assert Settings(_env_file=None).k8s_limits_budget_mib == 4096
