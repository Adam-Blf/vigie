from pathlib import Path

import numpy as np
import pytest

from drift_fakes import HashingEmbedder
from vigie.drift.reference import ReferenceSet, group_centroids


def test_group_centroids_are_sorted_by_group_and_unit_length() -> None:
    vectors = np.array([[0.0, 2.0], [1.0, 0.0], [0.0, 1.0]])
    centroids = group_centroids(vectors, ["RGPD", "DORA", "RGPD"])
    assert centroids[0] == pytest.approx([1.0, 0.0])
    assert centroids[1] == pytest.approx([0.0, 1.0])


def test_group_centroids_require_one_label_per_vector() -> None:
    with pytest.raises(ValueError, match="group labels"):
        group_centroids(np.eye(3), ["DORA"])


def test_reference_derives_baseline_and_centroid() -> None:
    reference = ReferenceSet(
        questions=np.array([[2.0, 0.0], [0.6, 0.8]]),
        anchors=np.array([[1.0, 0.0]]),
    )
    assert reference.dimension == 2
    assert reference.questions[0] == pytest.approx([1.0, 0.0])
    assert reference.baseline_similarity == pytest.approx([1.0, 0.6])
    assert reference.centroid == pytest.approx([0.8, 0.4])


def test_reference_rejects_a_single_question() -> None:
    with pytest.raises(ValueError, match="at least two"):
        ReferenceSet(questions=np.array([[1.0, 0.0]]), anchors=np.eye(2))


def test_reference_rejects_mismatched_dimensions() -> None:
    with pytest.raises(ValueError, match="dimension"):
        ReferenceSet(questions=np.eye(2), anchors=np.eye(3))


def test_reference_round_trips_through_npy_files(tmp_path: Path) -> None:
    reference = ReferenceSet(questions=np.eye(4)[:3], anchors=np.eye(4)[:2])
    questions_path = tmp_path / "drift" / "reference.npy"
    anchors_path = tmp_path / "drift" / "anchors.npy"

    reference.save(questions_path, anchors_path)
    loaded = ReferenceSet.load(questions_path, anchors_path)

    assert np.array_equal(loaded.questions, reference.questions)
    assert np.array_equal(loaded.anchors, reference.anchors)


def test_reference_builds_from_texts_with_one_anchor_per_regulation() -> None:
    embedder = HashingEmbedder()
    reference = ReferenceSet.from_texts(
        embedder,
        questions=["notification incident majeur", "bénéficiaire effectif vigilance"],
        anchor_texts=["incident majeur notification", "rapport incident", "vigilance client"],
        anchor_groups=["DORA", "DORA", "AMLR"],
    )
    assert reference.anchors.shape == (2, embedder.dimension)
    assert reference.questions.shape == (2, embedder.dimension)
