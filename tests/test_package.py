import guardbench
import vigie


def test_versions_are_exposed() -> None:
    assert vigie.__version__
    assert guardbench.__version__
