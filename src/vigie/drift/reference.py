"""The frozen picture of what normal traffic looks like.

Two matrices make up the reference. ``questions`` holds the embeddings of the golden
questions, the closest thing we have to real users before launch. ``anchors`` holds
the corpus centroids, one per regulation by default, against which every question is
scored to decide whether it is still about the corpus at all.

Both are stored as plain ``.npy`` files so the API image can load them without the
embedding model and without pickle.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from vigie.drift.embedder import Embedder, Matrix, normalize_rows


def group_centroids(vectors: Matrix, groups: Sequence[str]) -> Matrix:
    """Average the vectors of each group, then renormalize.

    Groups are sorted so the same corpus always yields the same anchor order, which
    keeps the saved file byte-identical across rebuilds.
    """
    matrix = normalize_rows(vectors)
    if len(groups) != matrix.shape[0]:
        raise ValueError(f"{len(groups)} group labels for {matrix.shape[0]} vectors")
    labels = np.asarray(groups)
    centroids = [matrix[labels == name].mean(axis=0) for name in sorted(set(groups))]
    return normalize_rows(np.stack(centroids))


@dataclass(frozen=True)
class ReferenceSet:
    questions: Matrix
    anchors: Matrix
    baseline_similarity: Matrix = field(init=False, repr=False)
    centroid: Matrix = field(init=False, repr=False)

    def __post_init__(self) -> None:
        questions = normalize_rows(self.questions)
        anchors = normalize_rows(self.anchors)
        if questions.shape[0] < 2:
            raise ValueError("the reference needs at least two questions")
        if questions.shape[1] != anchors.shape[1]:
            raise ValueError(
                f"questions have dimension {questions.shape[1]}, anchors {anchors.shape[1]}"
            )
        # The dataclass is frozen so callers cannot swap the reference under a running
        # monitor; object.__setattr__ is the documented way to fill derived fields.
        object.__setattr__(self, "questions", questions)
        object.__setattr__(self, "anchors", anchors)
        object.__setattr__(self, "baseline_similarity", (questions @ anchors.T).max(axis=1))
        object.__setattr__(self, "centroid", questions.mean(axis=0))

    @property
    def dimension(self) -> int:
        return int(self.questions.shape[1])

    @classmethod
    def from_texts(
        cls,
        embedder: Embedder,
        questions: Sequence[str],
        anchor_texts: Sequence[str],
        anchor_groups: Sequence[str],
    ) -> ReferenceSet:
        """Build the reference from golden questions and corpus passages."""
        anchors = group_centroids(embedder.embed(anchor_texts), anchor_groups)
        return cls(questions=embedder.embed(questions), anchors=anchors)

    def save(self, questions_path: Path, anchors_path: Path) -> None:
        for path, matrix in ((questions_path, self.questions), (anchors_path, self.anchors)):
            path.parent.mkdir(parents=True, exist_ok=True)
            np.save(path, matrix, allow_pickle=False)

    @classmethod
    def load(cls, questions_path: Path, anchors_path: Path) -> ReferenceSet:
        questions = np.load(questions_path, allow_pickle=False)
        anchors = np.load(anchors_path, allow_pickle=False)
        return cls(questions=questions, anchors=anchors)
