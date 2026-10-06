"""Benchmark samples: the in-house seed set and the public deepset control set.

The seed set is the one that decides which guard ships, so it carries its own
provenance (who labeled, who reviewed) and a frozen dev/test split. The deepset set
stays a separate control: it is English and German only and says nothing about the
French banking questions Vigie actually receives.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

Category = Literal[
    "benign",
    "benign_tricky",
    "direct_injection",
    "indirect_injection",
    "jailbreak",
    "system_prompt_leak",
    "pii",
    "unsafe_content",
    "tool_abuse",
]
CATEGORIES: tuple[Category, ...] = (
    "benign",
    "benign_tricky",
    "direct_injection",
    "indirect_injection",
    "jailbreak",
    "system_prompt_leak",
    "pii",
    "unsafe_content",
    "tool_abuse",
)
BENIGN_CATEGORIES: frozenset[str] = frozenset({"benign", "benign_tricky"})
Split = Literal["dev", "test"]
DEV_SHARE = 0.6


@dataclass(frozen=True)
class Sample:
    text: str
    malicious: bool
    category: str
    source: str
    lang: str
    split: str = "test"
    pair_id: str = ""
    labeled_by: str = ""
    reviewed_by: str = ""


def _pair_rank(pair_id: str) -> str:
    return hashlib.sha256(pair_id.encode("utf-8")).hexdigest()


def assign_splits(pair_ids: Iterable[str]) -> dict[str, Split]:
    """Split one category's pairs 60/40 by hash order.

    Hashing instead of shuffling means adding a pair later never moves the others, and
    both languages of a pair always land on the same side, so the test split never
    contains the translation of a dev sample.
    """
    ordered = sorted(set(pair_ids), key=_pair_rank)
    n_dev = round(len(ordered) * DEV_SHARE)
    return {pid: ("dev" if i < n_dev else "test") for i, pid in enumerate(ordered)}


def _sample_from_row(row: dict[str, Any]) -> Sample:
    category = str(row["category"])
    if category not in CATEGORIES:
        raise ValueError(f"unknown category {category!r} for sample {row.get('id')!r}")
    return Sample(
        text=str(row["text"]),
        malicious=bool(row["malicious"]),
        category=category,
        source=str(row.get("source", "vigie-seed")),
        lang=str(row["lang"]),
        split=str(row.get("split", "test")),
        pair_id=str(row.get("pair_id", "")),
        labeled_by=str(row.get("labeled_by", "")),
        reviewed_by=str(row.get("reviewed_by", "")),
    )


def load_seed(path: Path, split: str | None = None) -> list[Sample]:
    samples: list[Sample] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                samples.append(_sample_from_row(json.loads(line)))
    if split is None:
        return samples
    return [s for s in samples if s.split == split]


def deepset_rows_to_samples(rows: Sequence[dict[str, Any]]) -> list[Sample]:
    # deepset only says "injection or not". Filing every positive under direct_injection
    # keeps the per-category tables comparable without pretending to know the attack type.
    return [
        Sample(
            text=str(row["text"]),
            malicious=int(row["label"]) == 1,
            category="direct_injection" if int(row["label"]) == 1 else "benign",
            source="deepset/prompt-injections",
            lang="und",
            split="control",
        )
        for row in rows
    ]


def find_parquet(files: Sequence[str], split: str) -> str:
    """Pick the parquet file of one split; its name carries a hash that changes per upload."""
    candidates = [f for f in files if f.endswith(".parquet") and split in Path(f).name]
    if not candidates:
        raise FileNotFoundError(f"no parquet file for split {split!r} in {list(files)}")
    return sorted(candidates)[0]


def load_deepset(repo_id: str, split: str = "test") -> list[Sample]:
    from huggingface_hub import hf_hub_download, list_repo_files
    from pyarrow import parquet

    files = list_repo_files(repo_id, repo_type="dataset")
    local = hf_hub_download(repo_id, find_parquet(files, split), repo_type="dataset")
    rows: list[dict[str, Any]] = parquet.read_table(local).to_pylist()
    return deepset_rows_to_samples(rows)
