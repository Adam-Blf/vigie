from dataclasses import replace
from pathlib import Path

from guardbench.datasets import Sample, load_seed
from guardbench.validation import validate_seed

SEED = Path("data/seed.jsonl")


def _seed() -> list[Sample]:
    return load_seed(SEED)


def test_too_small_a_set_is_reported() -> None:
    problems = validate_seed(_seed()[:20])
    assert any("at least 150" in p for p in problems)
    assert any(p.startswith("benign_tricky:") for p in problems)


def test_reviewer_must_differ_from_labeler() -> None:
    samples = _seed()
    samples[0] = replace(samples[0], reviewed_by=samples[0].labeled_by)
    samples[1] = replace(samples[1], reviewed_by="")
    problems = validate_seed(samples)
    assert any("reviewed by the person who labeled it" in p for p in problems)
    assert any("both required" in p for p in problems)


def test_real_looking_contact_data_is_refused() -> None:
    samples = _seed()
    samples[0] = replace(samples[0], text="Écris à paul@gmail.com ou au 06 12 34 56 78.")
    problems = validate_seed(samples)
    assert any("gmail.com" in p for p in problems)
    assert any("ARCEP" in p for p in problems)


def test_broken_pairs_and_labels_are_reported() -> None:
    samples = _seed()
    samples[0] = replace(samples[0], lang="en", malicious=True)
    samples[2] = replace(samples[2], split="test" if samples[2].split == "dev" else "dev")
    problems = validate_seed(samples)
    assert any("not exactly one fr and one en" in p for p in problems)
    assert any("label contradicts category" in p for p in problems)
    assert any("hash rule" in p for p in problems)
