import numpy as np
import pytest

from vigie.drift.window import EmbeddingWindow


def test_window_starts_empty_with_the_right_shape() -> None:
    window = EmbeddingWindow(max_size=5, dimension=3)
    assert len(window) == 0
    assert window.matrix().shape == (0, 3)


def test_window_drops_the_oldest_rows_past_its_bound() -> None:
    window = EmbeddingWindow(max_size=3, dimension=2)
    for value in range(1, 6):
        window.add(np.array([float(value), 1.0]))
    assert len(window) == 3
    # Rows are normalized on the way in, so compare directions, not raw values.
    expected = np.array([[3.0, 1.0], [4.0, 1.0], [5.0, 1.0]])
    expected /= np.linalg.norm(expected, axis=1, keepdims=True)
    assert window.matrix() == pytest.approx(expected)


def test_window_add_reports_how_many_rows_came_in() -> None:
    window = EmbeddingWindow(max_size=10, dimension=2)
    assert window.add(np.eye(2)) == 2
    assert window.add(np.array([1.0, 0.0])) == 1


def test_window_rejects_a_foreign_dimension() -> None:
    window = EmbeddingWindow(max_size=3, dimension=2)
    with pytest.raises(ValueError, match="dimension 2"):
        window.add(np.eye(3))


@pytest.mark.parametrize(("max_size", "dimension"), [(0, 3), (3, 0)])
def test_window_rejects_degenerate_sizes(max_size: int, dimension: int) -> None:
    with pytest.raises(ValueError):
        EmbeddingWindow(max_size=max_size, dimension=dimension)
