import json
from pathlib import Path

import pytest

from vigie.loadtest.questions import (
    ATTACK_PROMPTS,
    BUILTIN_QUESTIONS,
    load_golden_questions,
    normal_questions,
)


def _write_jsonl(path: Path, rows: list[object]) -> None:
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n")


def test_missing_golden_dir_falls_back_to_builtin(tmp_path: Path) -> None:
    assert load_golden_questions(tmp_path / "absent") == []
    assert normal_questions(tmp_path / "absent") == list(BUILTIN_QUESTIONS)


def test_golden_questions_are_read_in_file_order(tmp_path: Path) -> None:
    _write_jsonl(tmp_path / "a.jsonl", [{"question": " Article 28 de DORA ? "}])
    _write_jsonl(
        tmp_path / "b.jsonl",
        [{"question": "What is a high-risk AI system?"}, {"id": "meta-only"}],
    )
    (tmp_path / "notes.txt").write_text("ignored", encoding="utf-8")
    assert normal_questions(tmp_path) == [
        "Article 28 de DORA ?",
        "What is a high-risk AI system?",
    ]


def test_rows_without_usable_question_are_skipped(tmp_path: Path) -> None:
    _write_jsonl(
        tmp_path / "golden.jsonl",
        [{"question": ""}, {"question": 42}, ["not", "a", "dict"], {"question": "Ok ?"}],
    )
    (tmp_path / "golden.jsonl").write_text(
        (tmp_path / "golden.jsonl").read_text(encoding="utf-8") + "\n   \n",
        encoding="utf-8",
    )
    assert load_golden_questions(tmp_path) == ["Ok ?"]


def test_empty_golden_set_falls_back_to_builtin(tmp_path: Path) -> None:
    _write_jsonl(tmp_path / "golden.jsonl", [{"id": 1}])
    assert normal_questions(tmp_path) == list(BUILTIN_QUESTIONS)


def test_corrupted_golden_line_raises(tmp_path: Path) -> None:
    (tmp_path / "golden.jsonl").write_text('{"question": "ok"}\n{broken\n', encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        load_golden_questions(tmp_path)


def test_builtin_lists_cover_both_languages() -> None:
    assert any("DORA" in q for q in BUILTIN_QUESTIONS)
    assert any(q.startswith("What") for q in BUILTIN_QUESTIONS)
    assert any(p.lower().startswith("ignore") for p in ATTACK_PROMPTS)
    assert len(set(ATTACK_PROMPTS)) == len(ATTACK_PROMPTS)
