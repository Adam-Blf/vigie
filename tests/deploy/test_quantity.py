import pytest

from vigie.deploy.quantity import MIB, cpu_millicores, memory_bytes


@pytest.mark.parametrize(
    ("value", "expected"),
    [("512Mi", 512 * MIB), ("1Gi", 1024 * MIB), ("1.5Gi", 1536 * MIB), ("64Ki", 65536)],
)
def test_binary_memory_units(value: str, expected: int) -> None:
    assert memory_bytes(value) == expected


def test_decimal_memory_units_and_bare_numbers() -> None:
    assert memory_bytes("1G") == 10**9
    assert memory_bytes("500M") == 500 * 10**6
    assert memory_bytes(1024) == 1024


@pytest.mark.parametrize(("value", "expected"), [("250m", 250), ("1", 1000), (0.5, 500)])
def test_cpu_units(value: str | float, expected: int) -> None:
    assert cpu_millicores(value) == expected


@pytest.mark.parametrize("value", ["12Xi", "lots", "", "-1Gi"])
def test_unknown_memory_quantity_is_refused(value: str) -> None:
    with pytest.raises(ValueError):
        memory_bytes(value)


def test_unknown_cpu_unit_is_refused() -> None:
    with pytest.raises(ValueError):
        cpu_millicores("2Gi")
