import json
import shutil
from pathlib import Path

import numpy as np
import pytest

from drift_fakes import FIXTURE, HashingEmbedder
from vigie.drift.cli import main
from vigie.drift.reference import ReferenceSet
from vigie.drift.sources import (
    FIXTURE_PATH,
    golden_reference_questions,
    load_passages,
    load_questions,
)

GOLDEN_ROWS = [
    {"question": "Qui notifie un incident majeur ?", "category": "in_scope", "status": "verified"},
    {"question": "Quel registre des prestataires TIC ?", "category": "in_scope", "split": "dev"},
    {"question": "Recette du gratin ?", "category": "out_of_scope", "status": "verified"},
    {"question": "Question piège sur DORA", "category": "trap", "status": "verified"},
    {"question": "Brouillon non relu", "category": "in_scope", "status": "draft"},
    {"question": "Question scellée", "category": "in_scope", "split": "test"},
]


def _write_jsonl(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = (json.dumps(row, ensure_ascii=False) for row in rows)
    path.write_text("\n".join(lines) + "\n\n", encoding="utf-8")


def _tiny_project(root: Path) -> None:
    _write_jsonl(root / "data" / "golden" / "questions.jsonl", GOLDEN_ROWS)
    _write_jsonl(
        root / "data" / "corpus" / "dora.jsonl",
        [
            {"regulation": "DORA", "text": "notification incident majeur autorité"},
            {"regulation": "DORA", "text": "registre prestataires services informatiques"},
        ],
    )
    _write_jsonl(
        root / "data" / "corpus" / "amlr.jsonl",
        [{"regulation": "AMLR", "text": "vigilance clientèle bénéficiaire effectif"}],
    )


def test_golden_keeps_only_verified_in_scope_questions_outside_the_test_split(
    tmp_path: Path,
) -> None:
    path = tmp_path / "questions.jsonl"
    _write_jsonl(path, GOLDEN_ROWS)
    assert golden_reference_questions(path) == [
        "Qui notifie un incident majeur ?",
        "Quel registre des prestataires TIC ?",
    ]


def test_golden_rejects_a_line_that_is_not_an_object(tmp_path: Path) -> None:
    path = tmp_path / "questions.jsonl"
    path.write_text('["not", "an", "object"]\n', encoding="utf-8")
    with pytest.raises(ValueError, match="line 1"):
        golden_reference_questions(path)


def test_sources_fall_back_to_the_fixture_without_golden_or_corpus(tmp_path: Path) -> None:
    (tmp_path / FIXTURE_PATH).parent.mkdir(parents=True)
    shutil.copy(FIXTURE, tmp_path / FIXTURE_PATH)

    questions, question_source = load_questions(None, tmp_path)
    passages, passage_sources = load_passages([], tmp_path)

    assert question_source == tmp_path / FIXTURE_PATH
    assert passage_sources == [tmp_path / FIXTURE_PATH]
    assert len(questions) == 34
    assert {passage.regulation for passage in passages} == {"DORA", "AIACT", "RGPD", "AMLR"}


def test_explicit_fixture_and_corpus_file_are_used_as_given(tmp_path: Path) -> None:
    _tiny_project(tmp_path)
    corpus_file = tmp_path / "data" / "corpus" / "amlr.jsonl"

    questions, _ = load_questions(FIXTURE, tmp_path)
    passages, sources = load_passages([corpus_file], tmp_path)

    assert len(questions) == 34
    assert sources == [corpus_file]
    assert [passage.regulation for passage in passages] == ["AMLR"]


def test_an_explicit_empty_corpus_directory_is_an_error(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(FileNotFoundError, match="no corpus JSONL"):
        load_passages([empty], tmp_path)


def test_build_reference_writes_questions_and_one_anchor_per_regulation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _tiny_project(tmp_path)
    embedder = HashingEmbedder(dimension=64)

    assert main(["build-reference"], embedder=embedder, root=tmp_path) == 0

    reference = ReferenceSet.load(
        tmp_path / "data" / "drift" / "reference.npy",
        tmp_path / "data" / "drift" / "anchors.npy",
    )
    assert reference.questions.shape == (2, 64)
    assert reference.anchors.shape == (2, 64)
    out = capsys.readouterr().out
    assert "questions: 2 from data/golden/questions.jsonl" in out
    assert "anchors: 2 from 3 passages in data/corpus/amlr.jsonl, data/corpus/dora.jsonl" in out
    assert "wrote data/drift/reference.npy and data/drift/anchors.npy" in out
    assert str(tmp_path) not in out


def test_build_reference_is_byte_identical_across_runs(tmp_path: Path) -> None:
    _tiny_project(tmp_path)
    args = ["build-reference", "--anchors-out", "a.npy", "--reference-out", "q.npy"]

    main(args, embedder=HashingEmbedder(dimension=32), root=tmp_path)
    first = (tmp_path / "a.npy").read_bytes(), (tmp_path / "q.npy").read_bytes()
    main(args, embedder=HashingEmbedder(dimension=32), root=tmp_path)

    assert ((tmp_path / "a.npy").read_bytes(), (tmp_path / "q.npy").read_bytes()) == first
    assert np.load(tmp_path / "a.npy").shape == (2, 32)


def test_paths_outside_the_working_directory_are_printed_as_given(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _tiny_project(tmp_path)
    outside = tmp_path.parent / f"{tmp_path.name}-out" / "q.npy"

    main(
        ["build-reference", "--reference-out", str(outside)],
        embedder=HashingEmbedder(dimension=16),
        root=tmp_path,
    )

    assert outside.is_file()
    assert outside.as_posix() in capsys.readouterr().out


def test_without_an_injected_embedder_the_configured_model_is_loaded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _tiny_project(tmp_path)
    loaded: list[str] = []

    def fake_model(name: str) -> HashingEmbedder:
        loaded.append(name)
        return HashingEmbedder(dimension=8)

    monkeypatch.setattr("vigie.drift.cli.FastEmbedEmbedder", fake_model)
    main(["build-reference", "--model", "tiny-model"], root=tmp_path)

    assert loaded == ["tiny-model"]
