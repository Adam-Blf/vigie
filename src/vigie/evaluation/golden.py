"""The golden question set: row model, loader, split assignment and the test seal.

The test split is sealed by a SHA-256 over its rows. Any edit to a test question, even a
comma, changes the digest, so tuning against the test set cannot happen by accident: the
validator refuses the file until someone deliberately writes a new seal, and that rewrite
shows up in review.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Category = Literal["in_scope", "out_of_scope", "trap"]
Split = Literal["dev", "test"]
Status = Literal["draft", "verified"]
Lang = Literal["fr", "en"]

# One question in three goes to the sealed test split, the rest is free for tuning.
TEST_SHARE_DENOMINATOR = 3


class GoldenQuestion(BaseModel):
    """One reference question, with what a correct answer has to cite."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    lang: Lang
    expected_articles: tuple[str, ...] = ()
    source_celex: str | None = None
    reference_quote: str | None = None
    reference_answer: str = Field(min_length=1)
    category: Category
    status: Status
    authored_by: str = Field(min_length=1)
    verified_by: str | None = None
    split: Split | None = None

    @property
    def expects_refusal(self) -> bool:
        return self.category == "out_of_scope"

    @property
    def regulations(self) -> frozenset[str]:
        # Partition instead of strict parsing: malformed ids are the validator's job to
        # report, and counting them under their prefix keeps the report readable.
        return frozenset(article.partition(":")[0] for article in self.expected_articles)


def parse_golden(lines: Iterable[str]) -> list[GoldenQuestion]:
    """Parse JSONL text, reporting the line number of the first malformed row."""
    questions: list[GoldenQuestion] = []
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            questions.append(GoldenQuestion.model_validate_json(line))
        except ValueError as exc:
            raise ValueError(f"line {line_number}: {exc}") from exc
    return questions


def load_golden(path: Path) -> list[GoldenQuestion]:
    return parse_golden(path.read_text(encoding="utf-8").splitlines())


def dump_golden(questions: Sequence[GoldenQuestion]) -> str:
    """Serialize back to JSONL in a stable form, so a rewrite only diffs what changed."""
    return "".join(
        json.dumps(q.model_dump(mode="json"), ensure_ascii=False) + "\n" for q in questions
    )


def _rank_key(question_id: str) -> str:
    # Hashing the id gives an order that looks random but never changes between runs or
    # machines, unlike a seeded shuffle that depends on the order rows were written in.
    return hashlib.sha256(question_id.encode("utf-8")).hexdigest()


def _stratum(question: GoldenQuestion) -> tuple[str, str, str]:
    regulation = ",".join(sorted(question.regulations)) or "-"
    return question.category, regulation, question.lang


def assign_splits(questions: Sequence[GoldenQuestion]) -> list[GoldenQuestion]:
    """Give every question a split, one third to test within each stratum.

    Strata are category, regulation and language, so the test split keeps the same mix
    as the whole set instead of, say, drawing every out-of-scope question by chance.
    """
    strata: dict[tuple[str, str, str], list[GoldenQuestion]] = {}
    for question in questions:
        strata.setdefault(_stratum(question), []).append(question)
    split_of: dict[str, Split] = {}
    for members in strata.values():
        ordered = sorted(members, key=lambda q: _rank_key(q.id))
        test_count = round(len(ordered) / TEST_SHARE_DENOMINATOR)
        for index, question in enumerate(ordered):
            split_of[question.id] = "test" if index < test_count else "dev"
    return [q.model_copy(update={"split": split_of[q.id]}) for q in questions]


def sealed_digest(questions: Iterable[GoldenQuestion]) -> str:
    """SHA-256 of the test rows, sorted by id and serialized with sorted keys."""
    rows = sorted((q for q in questions if q.split == "test"), key=lambda q: q.id)
    canonical = "\n".join(
        json.dumps(q.model_dump(mode="json"), ensure_ascii=False, sort_keys=True) for q in rows
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def read_seal(path: Path) -> str:
    return path.read_text(encoding="utf-8").split()[0]


def write_seal(path: Path, questions: Iterable[GoldenQuestion]) -> str:
    digest = sealed_digest(questions)
    path.write_text(f"{digest}  test split of questions.jsonl\n", encoding="utf-8")
    return digest
