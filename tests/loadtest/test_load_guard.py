import pytest

from vigie.loadtest.guard import (
    REMOTE_MAX_USERS,
    LoadGuardError,
    check_load_profile,
    is_local_host,
)


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:8710",
        "http://localhost:8710",
        "http://LOCALHOST",
        "http://127.0.0.2:8710",
        "http://[::1]:8710",
    ],
)
def test_loopback_hosts_are_local(url: str) -> None:
    assert is_local_host(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://vigie.141-145-1-2.sslip.io",
        "http://10.0.0.5:8710",
        "http://0.0.0.0:8710",
        "https://localhost.example.com",
        "http://127.0.0.1.nip.io",
        "not a url",
        "",
    ],
)
def test_other_hosts_are_not_local(url: str) -> None:
    assert not is_local_host(url)


def test_local_host_accepts_the_full_local_profile() -> None:
    check_load_profile("http://127.0.0.1:8710", 20)


def test_remote_host_accepts_the_liveness_cap() -> None:
    check_load_profile("https://vigie.example.org", REMOTE_MAX_USERS)


def test_remote_host_refuses_one_user_above_the_cap() -> None:
    with pytest.raises(LoadGuardError, match="limited to 8"):
        check_load_profile("https://vigie.example.org", REMOTE_MAX_USERS + 1)


def test_cap_is_the_production_rule() -> None:
    # The production rule is eight requests in flight; changing it needs a decision.
    assert REMOTE_MAX_USERS == 8


@pytest.mark.parametrize("host", [None, ""])
def test_missing_host_is_refused(host: str | None) -> None:
    with pytest.raises(LoadGuardError, match="no target host"):
        check_load_profile(host, 1)


def test_zero_users_is_refused() -> None:
    with pytest.raises(LoadGuardError, match="at least one user"):
        check_load_profile("http://127.0.0.1:8710", 0)
