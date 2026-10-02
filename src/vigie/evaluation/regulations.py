"""The four regulations the golden set may point at, by short code and CELEX number.

The corpus milestone owns the full source registry (titles, public links). The evaluation
only needs the code to CELEX mapping to check that a question and its articles agree, so
it keeps this small table instead of importing the ingestion code and its dependencies.
"""

from __future__ import annotations

REGULATION_CELEX: dict[str, str] = {
    "DORA": "32022R2554",
    "AIACT": "32024R1689",
    "RGPD": "32016R0679",
    "AMLR": "32024R1624",
}

CELEX_REGULATION: dict[str, str] = {celex: code for code, celex in REGULATION_CELEX.items()}


def article_id(regulation: str, article: str) -> str:
    """Build the dataset identifier of an article, for instance ``DORA:28``."""
    return f"{regulation}:{article}"


def split_article_id(value: str) -> tuple[str, str]:
    """Split ``DORA:28`` into its regulation code and article number.

    Raises ValueError on anything that is not ``CODE:ARTICLE`` with a known code, so a typo
    in the dataset surfaces as a clear message instead of a silent miss later on.
    """
    regulation, sep, article = value.partition(":")
    if not sep or not article or regulation not in REGULATION_CELEX:
        raise ValueError(f"malformed article id {value!r}, expected CODE:ARTICLE")
    return regulation, article
