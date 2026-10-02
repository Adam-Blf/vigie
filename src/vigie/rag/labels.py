"""Short regulation codes, citation labels and EUR-Lex links.

The label format "[DORA art. 28 §1]" is a contract shared with the prompt, the citation
validator, the API and the interface. It is built in one place so all four agree.
"""

from __future__ import annotations

REGULATIONS: dict[str, str] = {
    "DORA": "32022R2554",
    "AIACT": "32024R1689",
    "RGPD": "32016R0679",
    "AMLR": "32024R1624",
}

EURLEX_URL = "https://eur-lex.europa.eu/legal-content/FR/TXT/?uri=CELEX:{celex}"


def format_label(regulation: str, article: str, paragraph: str | None = None) -> str:
    suffix = f" §{paragraph}" if paragraph else ""
    return f"[{regulation} art. {article}{suffix}]"


def article_id(regulation: str, article: str) -> str:
    """Identifier used by the datasets, for example "DORA:28"."""
    return f"{regulation}:{article}"


def eurlex_url(regulation: str) -> str:
    return EURLEX_URL.format(celex=REGULATIONS[regulation])
