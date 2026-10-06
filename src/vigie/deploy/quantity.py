"""Parse Kubernetes resource quantities into plain integers.

Only the suffixes that appear in real manifests are accepted. An unknown suffix raises
instead of being read as zero, because a silently ignored limit would let the budget
check pass on a manifest that does not fit the node.
"""

from __future__ import annotations

import re
from decimal import Decimal

_BINARY = {"Ki": 2**10, "Mi": 2**20, "Gi": 2**30, "Ti": 2**40}
_DECIMAL = {"": 1, "k": 10**3, "M": 10**6, "G": 10**9, "T": 10**12}
_QUANTITY = re.compile(r"^(?P<num>[0-9]+(?:\.[0-9]+)?)(?P<unit>[A-Za-z]*)$")

MIB = 2**20


def _split(value: str | int | float) -> tuple[Decimal, str]:
    match = _QUANTITY.match(str(value).strip())
    if match is None:
        raise ValueError(f"not a Kubernetes quantity: {value!r}")
    return Decimal(match["num"]), match["unit"]


def memory_bytes(value: str | int | float) -> int:
    """Return a memory quantity such as `512Mi` or `1G` in bytes."""
    number, unit = _split(value)
    if unit in _BINARY:
        return int(number * _BINARY[unit])
    if unit in _DECIMAL:
        return int(number * _DECIMAL[unit])
    raise ValueError(f"unknown memory unit in {value!r}")


def cpu_millicores(value: str | int | float) -> int:
    """Return a CPU quantity such as `250m` or `1.5` in millicores."""
    number, unit = _split(value)
    if unit == "m":
        return int(number)
    if unit == "":
        return int(number * 1000)
    raise ValueError(f"unknown CPU unit in {value!r}")
