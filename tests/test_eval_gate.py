from pathlib import Path

import pytest
from tests.eval_fakes import report, thresholds

from vigie.evaluation.gate import passed, run_gate
from vigie.evaluation.thresholds import load_thresholds, parse_thresholds


def failing(checks: list) -> list[str]:  # type: ignore[type-arg]
    return [c.name for c in checks if not c.ok]


def test_the_versioned_file_is_read_as_written() -> None:
    t = thresholds()
    assert (t.split, t.k, t.recall_at_k_min, t.mrr_min) == ("test", 5, 0.80, 0.60)
    assert t.invented_in_final_answer_max == 0
    assert (t.max_drop, t.regression_metrics) == (0.02, ("recall_at_k", "raw_citation_validity"))
    assert (t.bootstrap_draws, t.bootstrap_seed, t.bootstrap_confidence) == (1000, 20261002, 0.95)


def test_a_missing_section_or_key_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="retrieval section"):
        parse_thresholds({"split": "test"})
    broken = tmp_path / "t.yaml"
    broken.write_text("- not a mapping\n", encoding="utf-8")
    with pytest.raises(ValueError, match="not a mapping"):
        load_thresholds(broken)
    data = {
        "split": "test",
        "retrieval": {"k": 5, "recall_at_k_min": 0.8},
        "citations": {},
        "refusal": {},
        "regression": {},
        "bootstrap": {},
    }
    with pytest.raises(ValueError, match="lacks mrr_min"):
        parse_thresholds(data)


def test_a_good_fake_llm_report_passes_and_model_floors_are_only_reported() -> None:
    checks = run_gate(report(), thresholds())
    assert passed(checks)
    precision = next(c for c in checks if c.name == "citation_precision")
    assert precision.ok and "reported only" in precision.note
    assert "PASS" in precision.line()


def test_retrieval_floors_and_invented_citations_always_gate() -> None:
    checks = run_gate(report(recall_at_k=0.79, mrr=0.5, invented_in_final_answer=1.0), thresholds())
    assert failing(checks) == ["recall_at_k", "mrr", "invented_in_final_answer"]
    assert checks[0].line().startswith("FAIL")


def test_a_real_llm_is_held_to_every_floor() -> None:
    checks = run_gate(report(llm="ministral-3:3b"), thresholds())
    assert failing(checks) == ["citation_precision", "correct_refusal_rate"]


def test_a_missing_metric_fails_instead_of_passing_silently() -> None:
    checks = run_gate(report(mrr=None), thresholds())
    assert failing(checks) == ["mrr"]
    assert "n/a" in checks[1].line()


def test_floors_only_apply_to_the_split_they_were_written_for() -> None:
    assert failing(run_gate(report(split="dev"), thresholds())) == ["split"]


def test_regression_against_the_champion_allows_two_points_not_more() -> None:
    champion = report(recall_at_k=0.87, raw_citation_validity=0.75)
    assert passed(run_gate(report(recall_at_k=0.85), thresholds(), champion))
    checks = run_gate(report(recall_at_k=0.84), thresholds(), champion)
    assert failing(checks) == ["recall_at_k vs champion"]
    assert "champion 0.8700" in checks[-2].line()


def test_regression_without_a_champion_value_or_with_a_missing_current_one() -> None:
    champion = report(raw_citation_validity=None)
    checks = run_gate(report(), thresholds(), champion)
    assert passed(checks)
    assert checks[-1].note == "no champion value"
    checks = run_gate(report(raw_citation_validity=None), thresholds(), report())
    assert "raw_citation_validity vs champion" in failing(checks)


def test_a_report_without_metrics_is_an_error() -> None:
    with pytest.raises(ValueError, match="no metrics"):
        run_gate({"split": "test"}, thresholds())
