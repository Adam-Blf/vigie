"""Find explicit article references in a question: "article 28 DORA", "Art. 6 AI Act".

Someone who names an article wants that article. Neither branch of the hybrid search
knows it: the dense vector of "article 28" is close to every article 28, and BM25 sees
"28" as one more token. On the J2 demo, "article 28 DORA" came out under DORA article 31.
The retriever puts the chunks of a referenced article first; this module only reads the
question, without any model, so the same question always gives the same references.

A number with no regulation named anywhere in the question is left alone: guessing
between the four article 28 would be worse than letting the search decide.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Longest names first inside each group so "AI Act" is not read as a stray "AI".
_ALIASES: dict[str, tuple[str, ...]] = {
    "DORA": (
        r"digital\s+operational\s+resilience\s+act",
        r"2022\s*/\s*2554",
        r"dora",
    ),
    "AIACT": (
        r"r[èe]glement\s+(?:europ[ée]en\s+)?sur\s+l['’]\s*(?:ia|intelligence\s+artificielle)",
        r"artificial\s+intelligence\s+act",
        r"2024\s*/\s*1689",
        r"ai\s*act",
        r"ia\s*act",
        r"aiact",
    ),
    "RGPD": (
        r"r[èe]glement\s+g[ée]n[ée]ral\s+sur\s+la\s+protection\s+des\s+donn[ée]es",
        r"general\s+data\s+protection\s+regulation",
        r"2016\s*/\s*679",
        r"rgpd",
        r"gdpr",
    ),
    "AMLR": (
        r"r[èe]glement\s+anti[\s-]?blanchiment",
        r"anti[\s-]?money\s+laundering\s+regulation",
        r"2024\s*/\s*1624",
        r"amlr",
    ),
}

# Word boundaries around the whole alternation: "adorable" must not read as DORA.
_REGULATION_RE = re.compile(
    r"\b(?:"
    + "|".join(f"(?P<{code}>{'|'.join(patterns)})" for code, patterns in _ALIASES.items())
    + r")\b",
    re.IGNORECASE,
)

# EU regulations number their articles with plain integers here; no "28a" in the four texts,
# and allowing a letter would read "article 28 a été" as article 28a.
_NUMBER = r"\d{1,3}"
# "article 28", "art. 6", "articles 28 et 30", "Articles 9, 10 and 15".
_ARTICLE_RE = re.compile(
    rf"\b(?:articles?|art\.?)\s*(?P<first>{_NUMBER})"
    rf"(?P<rest>(?:\s*(?:,|et|and|&|ou|or)\s*{_NUMBER})*)",
    re.IGNORECASE,
)
_LIST_ITEM_RE = re.compile(_NUMBER)


@dataclass(frozen=True)
class ArticleRef:
    regulation: str
    article: str

    @property
    def article_id(self) -> str:
        return f"{self.regulation}:{self.article}"


def _regulation_mentions(question: str) -> list[tuple[int, str]]:
    mentions: list[tuple[int, str]] = []
    for match in _REGULATION_RE.finditer(question):
        code = match.lastgroup
        if code is not None:
            mentions.append((match.start(), code))
    return mentions


def _article_numbers(question: str) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    for match in _ARTICLE_RE.finditer(question):
        found.append((match.start(), match.group("first")))
        rest_start = match.start("rest")
        for item in _LIST_ITEM_RE.finditer(match.group("rest")):
            found.append((rest_start + item.start(), item.group()))
    return found


def parse_references(question: str) -> list[ArticleRef]:
    """References in order of appearance, without duplicates.

    Each number goes to the nearest regulation named in the question, which handles both
    "article 28 DORA" and "DORA, article 28" and keeps "art. 5 AI Act et art. 6 RGPD" apart.
    """
    mentions = _regulation_mentions(question)
    if not mentions:
        return []
    refs: dict[str, ArticleRef] = {}
    for position, number in _article_numbers(question):
        _, code = min(mentions, key=lambda mention: abs(mention[0] - position))
        ref = ArticleRef(code, number)
        refs.setdefault(ref.article_id, ref)
    return list(refs.values())
