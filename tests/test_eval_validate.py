from pathlib import Path
from typing import Any

import pytest

from test_eval_golden import make
from vigie.evaluation.cli import main
from vigie.evaluation.golden import GoldenQuestion, dump_golden, sealed_digest, write_seal
from vigie.evaluation.validate import validate_golden

CORPUS = {
    "RGPD:33": "Article 33 si possible, 72 heures au plus tard après en avoir pris connaissance",
    "DORA:28": "Article 28 Principes généraux 1. Les entités financières gèrent les risques",
}


def golden_set(**overrides: Any) -> list[GoldenQuestion]:
    questions = [
        make("in-1", split="test", **overrides),
        make("in-2"),
        make(
            "oos-1",
            category="out_of_scope",
            expected_articles=[],
            source_celex=None,
            reference_quote=None,
        ),
    ]
    return questions


def messages(questions: list[GoldenQuestion]) -> list[str]:
    report = validate_golden(questions, CORPUS, sealed_digest(questions))
    return [str(issue) for issue in report.issues]


def test_clean_set_passes_and_is_counted() -> None:
    questions = golden_set()
    report = validate_golden(questions, CORPUS, sealed_digest(questions))
    assert report.ok
    assert report.counts["regulation"] == {"RGPD": 2, "none": 1}
    assert report.counts["category"] == {"in_scope": 2, "out_of_scope": 1}
    assert report.counts["split"] == {"test": 1, "dev": 2}


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"status": "draft"}, "only verified rows"),
        ({"verified_by": None}, "verified_by is empty"),
        ({"verified_by": "Emilien Morice"}, "verified by its own author"),
        ({"expected_articles": ["RGPD:999"]}, "unknown article RGPD:999"),
        ({"expected_articles": ["RGPD33"]}, "malformed article id"),
        ({"expected_articles": ["DORA:28"]}, "does not belong to CELEX"),
        ({"expected_articles": []}, "no expected article"),
        ({"reference_quote": None}, "reference_quote is empty"),
        ({"reference_quote": "48 heures au plus tard"}, "not found"),
    ],
)
def test_each_rule_is_enforced(overrides: dict[str, Any], expected: str) -> None:
    found = messages([make("bad", **overrides), *golden_set()[1:]])
    assert any(expected in message for message in found), found


def test_quote_matches_across_non_breaking_spaces() -> None:
    questions = [make("q", reference_quote="72 heures  au plus tard"), *golden_set()[1:]]
    assert not any("not found" in m for m in messages(questions))


def test_out_of_scope_cannot_carry_a_quote() -> None:
    questions = [*golden_set()[:2], make("oos", category="out_of_scope", expected_articles=[])]
    assert any("out-of-scope question cannot" in m for m in messages(questions))


def test_missing_split_duplicates_and_share_are_reported() -> None:
    questions = [make("a", split=None), make("a"), make("b")]
    found = messages(questions)
    assert "a: split is missing" in found
    assert "a: duplicate id" in found
    assert any("test share is 0.00" in m for m in found)


def test_seal_mismatch_and_absence_are_reported() -> None:
    questions = golden_set()
    assert not validate_golden(questions, CORPUS, "0" * 64).ok
    report = validate_golden(questions, CORPUS, None)
    assert any("no test seal" in str(i) for i in report.issues)


@pytest.fixture
def files(tmp_path: Path) -> tuple[Path, Path, Path]:
    golden = tmp_path / "questions.jsonl"
    golden.write_text(dump_golden(golden_set()), encoding="utf-8")
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    lines = [
        f'{{"regulation": "{k.split(":")[0]}", "article": "{k.split(":")[1]}", "text": "{v}"}}'
        for k, v in CORPUS.items()
    ]
    (corpus / "all.jsonl").write_text("\n".join(lines), encoding="utf-8")
    return golden, tmp_path / "test.sha256", corpus


def test_cli_validates_after_sealing(
    files: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    golden, seal, corpus = files
    common = ["--golden", str(golden), "--seal", str(seal)]
    assert main(["validate-golden", *common, "--corpus", str(corpus)]) == 1
    assert "no test seal" in capsys.readouterr().out
    assert main(["seal-golden", *common]) == 0
    assert main(["validate-golden", *common, "--corpus", str(corpus)]) == 0
    out = capsys.readouterr().out
    assert "golden set OK" in out
    assert "by regulation: RGPD=2, none=1" in out


def test_cli_refuses_silent_reseal(
    files: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    golden, seal, _ = files
    write_seal(seal, [make("other", split="test")])
    common = ["--golden", str(golden), "--seal", str(seal)]
    assert main(["seal-golden", *common]) == 1
    assert "--force" in capsys.readouterr().err
    assert main(["seal-golden", *common, "--force"]) == 0


def test_cli_refuses_to_seal_rows_without_split(
    files: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    golden, seal, _ = files
    golden.write_text(dump_golden([make("a", split=None)]), encoding="utf-8")
    assert main(["seal-golden", "--golden", str(golden), "--seal", str(seal)]) == 1
    assert "needs a split" in capsys.readouterr().err


def test_empty_set_only_misses_its_seal() -> None:
    report = validate_golden([], CORPUS, sealed_digest([]))
    assert report.ok
