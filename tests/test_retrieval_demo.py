import io
from pathlib import Path

from scripts.retrieval_demo import QUESTIONS, TOP, main
from tests.retrieval_fixtures import FakeEmbedder, indexed_settings


def test_demo_prints_top_five_for_the_three_default_questions(tmp_path: Path) -> None:
    out = io.StringIO()
    assert main([], out, indexed_settings(tmp_path), FakeEmbedder()) == 0
    text = out.getvalue()
    for number, question in enumerate(QUESTIONS, 1):
        assert f"Q{number}. {question}" in text
    # The mini corpus holds five chunks, so each question lists all of them.
    assert text.count("rrf=") == TOP * len(QUESTIONS)


def test_demo_takes_its_own_questions(tmp_path: Path) -> None:
    out = io.StringIO()
    assert main(["article 28 DORA"], out, indexed_settings(tmp_path), FakeEmbedder()) == 0
    lines = out.getvalue().splitlines()
    assert lines[1] == "Q1. article 28 DORA"
    assert lines[2].startswith("  1. [DORA art. 28 §1]")
