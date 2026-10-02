"""Refuse a load test that could hurt a shared or production deployment.

The rule comes from an incident on another project: fifty requests in flight against a
production site tripped the host's mitigation and took the site down for everyone for
twenty-five minutes. Since then, anything that is not this machine gets at most eight
concurrent users, which is a liveness check, not a search for the limit.

Each Locust user keeps at most one request in flight, so capping users caps requests in
flight. The cap is a constant rather than a setting on purpose: an environment variable
is exactly what someone would raise in a hurry, and this guard exists for that moment.
"""

from __future__ import annotations

import ipaddress
from urllib.parse import urlsplit

REMOTE_MAX_USERS = 8
_LOCAL_NAMES = frozenset({"localhost"})


class LoadGuardError(RuntimeError):
    """Raised when a load profile is not allowed against the requested host."""


def is_local_host(host_url: str) -> bool:
    """Tell whether ``host_url`` points at this machine (localhost or a loopback address)."""
    hostname = urlsplit(host_url).hostname
    if not hostname:
        return False
    if hostname.lower() in _LOCAL_NAMES:
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        # A domain name other than localhost: we cannot prove it is local, so it is not.
        return False


def check_load_profile(host_url: str | None, users: int) -> None:
    """Validate a run before the first user spawns.

    A missing host is refused too: Locust would otherwise fall back to whatever the user
    classes declare, and the guard would be judging a host it never saw.
    """
    if users < 1:
        raise LoadGuardError(f"at least one user is needed, got {users}")
    if not host_url:
        raise LoadGuardError("no target host given, pass --host explicitly")
    if not is_local_host(host_url) and users > REMOTE_MAX_USERS:
        raise LoadGuardError(
            f"{users} users against {host_url} refused: a host that is not local is "
            f"limited to {REMOTE_MAX_USERS} concurrent users (liveness check only). "
            "Search for the limit on 127.0.0.1."
        )
