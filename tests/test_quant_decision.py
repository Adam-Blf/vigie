from pathlib import Path

import pytest
from pydantic import ValidationError

from vigie.quant.decision import (
    QuantThreshold,
    VariantResult,
    compare,
    decide,
    load_threshold,
)

ROOT = Path(__file__).resolve().parent.parent
THRESHOLD = QuantThreshold(split="dev", k=5, max_recall_drop=0.02, max_size_ratio=0.5)


def result(name: str, size: int, recall: float, questions: int = 47) -> VariantResult:
    return VariantResult(name, size, recall, 0.4, 10.0, 20.0, questions)


@pytest.mark.parametrize(
    ("drop", "ratio", "keep"),
    [
        (0.0, 0.25, True),
        (-0.04, 0.25, True),  # int8 better than fp32 is still a keep
        (0.02, 0.5, True),  # both limits are inclusive
        (0.6 - 0.58, 0.5, True),  # 0.020000000000000018, the float noise of a mean
        (0.021, 0.25, False),
        (0.0, 0.51, False),
        (0.05, 0.9, False),
    ],
)
def test_keep_int8_iff_recall_drop_and_size_ratio_hold(
    drop: float, ratio: float, keep: bool
) -> None:
    kept, reasons = decide(recall_drop=drop, size_ratio=ratio, threshold=THRESHOLD)
    assert kept is keep
    assert (reasons == ()) is keep


def test_each_failed_condition_gives_its_own_reason() -> None:
    _, reasons = decide(recall_drop=0.05, size_ratio=0.9, threshold=THRESHOLD)
    assert len(reasons) == 2
    assert "5.0 points" in reasons[0]
    assert "0.90 of fp32" in reasons[1]


def test_compare_builds_the_decision_from_two_variants() -> None:
    decision = compare(result("fp32", 400, 0.50), result("int8", 100, 0.49), THRESHOLD)
    assert decision.keep_int8
    assert decision.deployed == "int8"
    assert decision.size_ratio == 0.25
    assert decision.recall_drop == pytest.approx(0.01)


def test_compare_keeps_fp32_when_int8_loses_too_much_recall() -> None:
    decision = compare(result("fp32", 400, 0.50), result("int8", 100, 0.45), THRESHOLD)
    assert not decision.keep_int8
    assert decision.deployed == "fp32"


@pytest.mark.parametrize(
    ("fp32", "int8"),
    [
        (result("fp32", 0, 0.5), result("int8", 100, 0.5)),
        (result("fp32", 400, 0.5), result("int8", 100, 0.5, questions=10)),
    ],
)
def test_compare_rejects_inconsistent_measurements(
    fp32: VariantResult, int8: VariantResult
) -> None:
    with pytest.raises(ValueError):
        compare(fp32, int8, THRESHOLD)


def test_the_versioned_threshold_is_the_one_of_the_brief() -> None:
    threshold = load_threshold(ROOT / "eval" / "thresholds.yaml")
    assert threshold == THRESHOLD


def test_a_threshold_on_the_test_split_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "t.yaml"
    path.write_text(
        "quantization:\n  split: test\n  k: 5\n  max_recall_drop: 0.02\n  max_size_ratio: 0.5\n",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError):
        load_threshold(path)


@pytest.mark.parametrize("content", ["version: 1\n", "- a list\n"])
def test_a_file_without_quantization_section_is_refused(tmp_path: Path, content: str) -> None:
    path = tmp_path / "t.yaml"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError, match="no quantization section"):
        load_threshold(path)
