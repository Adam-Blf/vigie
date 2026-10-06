"""Checks on the committed golden set that need no corpus, so they run in every CI job.

The quote check needs the regulation texts and runs through ``vigie-eval validate-golden``;
what is tested here is the shape the evaluation protocol promises.
"""

from collections import Counter
from pathlib import Path

from vigie.evaluation.golden import load_golden, read_seal, sealed_digest

GOLDEN = Path(__file__).resolve().parents[1] / "data" / "golden"
QUESTIONS = load_golden(GOLDEN / "questions.jsonl")


def test_size_and_mix_follow_the_protocol() -> None:
    assert len(QUESTIONS) >= 80
    categories = Counter(q.category for q in QUESTIONS)
    assert categories["out_of_scope"] == 10
    assert categories["trap"] == 10
    french = sum(q.lang == "fr" for q in QUESTIONS) / len(QUESTIONS)
    assert 0.68 <= french <= 0.72


def test_every_regulation_has_at_least_ten_questions() -> None:
    per_regulation = Counter(code for q in QUESTIONS for code in q.regulations)
    assert set(per_regulation) == {"DORA", "AIACT", "RGPD", "AMLR"}
    assert min(per_regulation.values()) >= 10


def test_rows_are_verified_by_the_other_member() -> None:
    assert all(q.status == "verified" for q in QUESTIONS)
    assert all(q.verified_by and q.verified_by != q.authored_by for q in QUESTIONS)


def test_test_split_matches_its_seal() -> None:
    assert read_seal(GOLDEN / "test.sha256") == sealed_digest(QUESTIONS)
    assert len({q.id for q in QUESTIONS}) == len(QUESTIONS)
