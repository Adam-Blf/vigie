from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from vigie.evaluation.golden import (
    GoldenQuestion,
    assign_splits,
    dump_golden,
    load_golden,
    parse_golden,
    read_seal,
    sealed_digest,
    write_seal,
)


def make(qid: str, **overrides: Any) -> GoldenQuestion:
    row: dict[str, Any] = {
        "id": qid,
        "question": "Quel délai pour notifier une violation ?",
        "lang": "fr",
        "expected_articles": ["RGPD:33"],
        "source_celex": "32016R0679",
        "reference_quote": "72 heures au plus tard",
        "reference_answer": "72 heures.",
        "category": "in_scope",
        "status": "verified",
        "authored_by": "Emilien Morice",
        "verified_by": "Adam Beloucif",
        "split": "dev",
    }
    row.update(overrides)
    return GoldenQuestion.model_validate(row)


def test_round_trip_through_jsonl(tmp_path: Path) -> None:
    questions = [make("a"), make("b", category="out_of_scope", expected_articles=[])]
    path = tmp_path / "q.jsonl"
    path.write_text(dump_golden(questions), encoding="utf-8")
    assert load_golden(path) == questions


def test_out_of_scope_expects_refusal_and_no_regulation() -> None:
    question = make("x", category="out_of_scope", expected_articles=[])
    assert question.expects_refusal
    assert question.regulations == frozenset()
    assert make("y").regulations == {"RGPD"}


def test_parse_reports_the_bad_line() -> None:
    good = dump_golden([make("a")])
    with pytest.raises(ValueError, match="line 3"):
        parse_golden([good, "", '{"id": "b"}'])


def test_unknown_field_is_rejected() -> None:
    with pytest.raises(ValueError):
        make("a", note="free text")


def test_assign_splits_is_stratified_and_stable() -> None:
    questions = [make(f"fr-{i}") for i in range(9)] + [
        make(f"oos-{i}", category="out_of_scope", expected_articles=[]) for i in range(3)
    ]
    first = assign_splits(questions)
    assert [q.id for q in first] == [q.id for q in questions]
    assert first == assign_splits(list(reversed(questions)))[::-1]
    by_stratum = Counter((q.category, q.split) for q in first)
    assert by_stratum == {
        ("in_scope", "test"): 3,
        ("in_scope", "dev"): 6,
        ("out_of_scope", "test"): 1,
        ("out_of_scope", "dev"): 2,
    }


def test_digest_covers_test_rows_only() -> None:
    questions = [make("a", split="test"), make("b", split="dev")]
    digest = sealed_digest(questions)
    assert digest == sealed_digest(list(reversed(questions)))
    assert digest == sealed_digest([questions[0], make("b", split="dev", question="autre")])
    assert digest != sealed_digest([make("a", split="test", question="autre"), questions[1]])


def test_seal_file_round_trip(tmp_path: Path) -> None:
    questions = [make("a", split="test")]
    path = tmp_path / "test.sha256"
    digest = write_seal(path, questions)
    assert read_seal(path) == digest
    assert path.read_text(encoding="utf-8").startswith(digest + "  ")
