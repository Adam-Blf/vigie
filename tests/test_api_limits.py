from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api_fixtures import FailingLLM, make_api
from vigie.api.ratelimit import SlidingWindowLimiter
from vigie.api.usage import UsageEvent


def test_rate_limit_gives_429_with_retry_after(tmp_path: Path) -> None:
    api = make_api(tmp_path, rate_limit_per_minute=2)
    assert [api.ask().status_code for _ in range(2)] == [200, 200]
    response = api.ask()
    assert response.status_code == 429
    assert response.json()["error"] == "rate_limited"
    assert 1 <= int(response.headers["retry-after"]) <= 60


def test_rate_limit_is_per_token(tmp_path: Path) -> None:
    api = make_api(tmp_path, rate_limit_per_minute=1)
    assert api.ask().status_code == 200
    other = api.client.post(
        "/v1/ask", json={"question": "Bonjour DORA"}, headers=api.auth(api.admin_token)
    )
    assert other.status_code == 200


def test_daily_quota_gives_429_until_midnight(tmp_path: Path) -> None:
    api = make_api(tmp_path, daily_quota=2)
    assert [api.ask().status_code for _ in range(2)] == [200, 200]
    response = api.ask()
    assert response.status_code == 429
    assert response.json()["error"] == "quota_exceeded"
    assert 1 <= int(response.headers["retry-after"]) <= 86400
    # Refused requests are not counted, so the quota page still says 2.
    assert api.client.get("/v1/usage/me", headers=api.auth()).json()["requests_today"] == 2


def test_maintenance_switch_closes_v1_but_not_liveness(tmp_path: Path) -> None:
    api = make_api(tmp_path, maintenance=True)
    response = api.ask()
    assert response.status_code == 503
    assert response.json()["error"] == "maintenance"
    assert response.headers["retry-after"] == "10"
    assert api.client.get("/v1/usage/me").status_code == 503
    assert api.client.get("/readyz").status_code == 503
    assert api.client.get("/healthz").status_code == 200


@pytest.mark.parametrize(
    ("kind", "status", "retry"),
    [("overloaded", 503, True), ("unavailable", 503, True), ("timeout", 504, False)],
)
def test_llm_failures_map_to_status_and_own_counter(
    tmp_path: Path, kind: str, status: int, retry: bool
) -> None:
    api = make_api(tmp_path, llm=FailingLLM(kind))  # type: ignore[arg-type]
    response = api.ask()
    assert response.status_code == status
    assert response.json() == {"error": f"llm_{kind}", "trace_id": response.headers["x-trace-id"]}
    assert ("retry-after" in response.headers) is retry
    metrics = api.client.get("/metrics").text
    assert f'vigie_llm_errors_total{{bundle_version="test-bundle",kind="{kind}"}} 1.0' in metrics
    assert "vigie_errors_total{" not in metrics
    # The slot was given back: the next call fails the same way instead of "busy".
    assert api.ask().json()["error"] == f"llm_{kind}"


def test_other_llm_failure_is_a_bad_gateway(tmp_path: Path) -> None:
    api = make_api(tmp_path, llm=FailingLLM("model"))
    assert api.ask().status_code == 502


def test_no_free_generation_slot_gives_503(tmp_path: Path) -> None:
    api = make_api(tmp_path, llm_max_inflight=1)
    assert api.state.llm_slots.acquire(blocking=False)
    response = api.ask()
    assert response.status_code == 503
    assert response.json()["error"] == "llm_busy"
    assert response.headers["retry-after"] == "10"


def test_fault_injection_fails_like_a_broken_build(tmp_path: Path) -> None:
    api = make_api(tmp_path, fault_error_rate=0.3)
    api.state.random = lambda: 0.1
    response = api.ask()
    assert response.status_code == 500
    assert response.json()["error"] == "internal_error"
    assert 'kind="fault_injection"' in api.client.get("/metrics").text
    api.state.random = lambda: 0.9
    assert api.ask().status_code == 200


def test_fault_injection_is_off_by_default(tmp_path: Path) -> None:
    api = make_api(tmp_path)
    api.state.random = lambda: 0.0
    assert api.ask().status_code == 200


def test_unexpected_error_is_generic(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    api = make_api(tmp_path)

    def broken(event: UsageEvent) -> None:
        raise RuntimeError("disk /var/lib/vigie full")

    api.state.usage.record = broken  # type: ignore[method-assign]
    client = TestClient(api.client.app, raise_server_exceptions=False)
    response = client.post("/v1/ask", json={"question": "Bonjour"}, headers=api.auth())
    assert response.status_code == 500
    assert response.json()["error"] == "internal_error"
    assert "/var/lib" not in response.text


def test_sliding_window_frees_slots_as_time_passes() -> None:
    now = [0.0]
    limiter = SlidingWindowLimiter(2, clock=lambda: now[0])
    assert limiter.acquire("t") is None and limiter.acquire("t") is None
    assert limiter.acquire("t") == 60
    now[0] = 30.0
    assert limiter.acquire("t") == 30
    now[0] = 60.0
    assert limiter.acquire("t") is None
