"""Citation extraction and validation against the passages actually given to the model.

A small model will sometimes cite an article it never saw. The rule is simple: a label
survives only if a provided passage backs it, everything else is cut from the text and
reported, so the final answer can never point a compliance officer to an invented article.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field

from vigie.rag.labels import format_label
from vigie.rag.types import Citation, Passage

# Tolerant on purpose: models write "art." or "article", "§1", "§ 1" or "paragraphe 1".
# Any bracketed "[CODE art. N]" is caught, even with an unknown code, so that a citation
# to a regulation outside the corpus is removed instead of slipping through untouched.
LABEL_RE = re.compile(
    r"(?P<space>[ \t]*)\[\s*(?P<code>[A-Za-z][A-Za-z0-9]{1,9})\s+art(?:icle|\.)?\s*"
    r"(?P<article>\d+[a-z]?)"
    r"(?:\s*,?\s*(?:§|paragraphe|par\.)\s*(?P<paragraph>\d+[a-z]?))?\s*\]"
)

EXCERPT_CHARS = 240


@dataclass(frozen=True)
class RawCitation:
    regulation: str
    article: str
    paragraph: str | None

    @property
    def label(self) -> str:
        return format_label(self.regulation, self.article, self.paragraph)


@dataclass
class CitationReport:
    text: str
    citations: list[Citation] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    raw_total: int = 0
    raw_valid: int = 0

    @property
    def raw_valid_rate(self) -> float | None:
        """Share of raw citations that were valid before filtering, None if none at all."""
        return self.raw_valid / self.raw_total if self.raw_total else None


def _parse(match: re.Match[str]) -> RawCitation:
    return RawCitation(
        regulation=match["code"].upper(),
        article=match["article"],
        paragraph=match["paragraph"],
    )


def extract_citations(text: str) -> list[RawCitation]:
    return [_parse(m) for m in LABEL_RE.finditer(text)]


def find_support(raw: RawCitation, passages: Sequence[Passage]) -> Passage | None:
    """Return the passage that backs a citation, or None when nothing does.

    A passage without a paragraph covers its whole article, so it supports a citation to
    any paragraph of that article. A citation without a paragraph is backed by any
    passage of the article.
    """
    same_article = [
        p for p in passages if p.regulation == raw.regulation and p.article == raw.article
    ]
    if raw.paragraph is None:
        return same_article[0] if same_article else None
    for passage in same_article:
        if passage.paragraph == raw.paragraph:
            return passage
    for passage in same_article:
        if passage.paragraph is None:
            return passage
    return None


def _excerpt(text: str) -> str:
    if len(text) <= EXCERPT_CHARS:
        return text
    cut = text[:EXCERPT_CHARS].rsplit(" ", 1)[0]
    return f"{cut}..."


def validate_citations(text: str, passages: Sequence[Passage]) -> CitationReport:
    report = CitationReport(text=text)
    seen: set[str] = set()

    def replace(match: re.Match[str]) -> str:
        raw = _parse(match)
        report.raw_total += 1
        support = find_support(raw, passages)
        if support is None:
            report.removed.append(raw.label)
            # Dropping the leading space too keeps "phrase [X]." from becoming "phrase ."
            return ""
        report.raw_valid += 1
        if raw.label not in seen:
            seen.add(raw.label)
            report.citations.append(
                Citation(
                    label=raw.label,
                    regulation=raw.regulation,
                    article=raw.article,
                    paragraph=raw.paragraph,
                    excerpt=_excerpt(support.text),
                    url=support.url,
                )
            )
        return f"{match['space']}{raw.label}"

    report.text = LABEL_RE.sub(replace, text).strip()
    return report
