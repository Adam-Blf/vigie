"""Rules the seed set must satisfy before any number computed on it is published.

Each rule exists because breaking it silently skews the benchmark: a translated test
sample leaking into dev, a label nobody reviewed, or a phone number that belongs to a
real person in a public repository.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Sequence

from guardbench.datasets import BENIGN_CATEGORIES, CATEGORIES, Sample, assign_splits

MIN_TOTAL = 150
MIN_PER_CATEGORY = 12
MIN_BY_CATEGORY = {"benign_tricky": 40, "indirect_injection": 30}
LANGS = frozenset({"fr", "en"})

_EMAIL = re.compile(r"[\w.+-]+@([\w-]+(?:\.[\w-]+)+)")
_PHONE = re.compile(r"(?<!\d)0[1-9](?:[ .]?\d{2}){4}(?!\d)")
# ARCEP keeps 01 99 00 xx xx free for fiction; anything else could ring a real line.
_FICTION_PHONE = re.compile(r"^01[ .]?99[ .]?00")


def _count_problems(samples: Sequence[Sample]) -> list[str]:
    problems = []
    if len(samples) < MIN_TOTAL:
        problems.append(f"{len(samples)} samples, at least {MIN_TOTAL} expected")
    counts = Counter(s.category for s in samples)
    for category in CATEGORIES:
        floor = MIN_BY_CATEGORY.get(category, MIN_PER_CATEGORY)
        if counts[category] < floor:
            problems.append(f"{category}: {counts[category]} samples, at least {floor}")
    return problems


def _pair_problems(samples: Sequence[Sample]) -> list[str]:
    problems = []
    pairs: dict[str, list[Sample]] = defaultdict(list)
    for sample in samples:
        pairs[sample.pair_id].append(sample)
    for pair_id, members in pairs.items():
        if sorted(m.lang for m in members) != sorted(LANGS):
            problems.append(f"pair {pair_id!r} is not exactly one fr and one en sample")
        if len({(m.category, m.malicious, m.split) for m in members}) != 1:
            problems.append(f"pair {pair_id!r} disagrees on category, label or split")
    by_category: dict[str, set[str]] = defaultdict(set)
    for sample in samples:
        by_category[sample.category].add(sample.pair_id)
    for pair_ids in by_category.values():
        expected = assign_splits(pair_ids)
        for sample in samples:
            if sample.pair_id in expected and sample.split != expected[sample.pair_id]:
                problems.append(f"pair {sample.pair_id!r} split differs from the hash rule")
                break
    return problems


def _sample_problems(sample: Sample) -> list[str]:
    problems = []
    ident = f"{sample.pair_id}/{sample.lang}"
    if sample.malicious == (sample.category in BENIGN_CATEGORIES):
        problems.append(f"{ident}: label contradicts category {sample.category}")
    if not sample.labeled_by or not sample.reviewed_by:
        problems.append(f"{ident}: labeled_by and reviewed_by are both required")
    elif sample.labeled_by == sample.reviewed_by:
        problems.append(f"{ident}: reviewed by the person who labeled it")
    for domain in _EMAIL.findall(sample.text):
        if domain.lower() != "example.com" and not domain.lower().endswith(".example.com"):
            problems.append(f"{ident}: e-mail domain {domain} is not example.com")
    for phone in _PHONE.findall(sample.text):
        if not _FICTION_PHONE.match(phone):
            problems.append(f"{ident}: phone {phone} is outside the ARCEP fiction range")
    return problems


def validate_seed(samples: Sequence[Sample]) -> list[str]:
    problems = _count_problems(samples) + _pair_problems(samples)
    for sample in samples:
        problems.extend(_sample_problems(sample))
    return problems
