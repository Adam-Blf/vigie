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

# Tolerant on purpose: anything in brackets that reads like a regulation citation is
# caught, whatever the spelling, so that an unbacked one is removed instead of slipping
# through untouched. Models write "art." or "article", "§1", "§ 1" or "paragraphe 1",
# put a comma after the code, use an alias ("AI Act", "GDPR", "LCB-FT"), lowercase it, or
# put the article first ("[art. 6 RGPD]"). An unknown code is still caught, and since no
# passage carries it, the citation is removed.
# Ministral 3B also adds the point under a paragraph ("§4 a", "§4, point c)"). Chunks stop
# at the paragraph, so the point is read and dropped: the label is checked at that level.
_CODE = (
    r"(?:(?:r[èe]glement|regulation)\s+)?"
    r"(?P<{name}>[^\W\d_][\w-]{{0,9}}(?:[ -]\w{{1,6}}){{0,2}})"
)
_ART = r"art(?:icle|\.)?\s*(?P<{name}>\d+[a-z]?)"
_PARA = r"\s*,?\s*(?:§|paragraphe?|para\.?|par\.)\s*(?P<{name}>\d+[a-z]?)"
_POINT = r"(?:\s*,?\s*(?:point\s*)?\(?[a-z]{1,4}\))"
_BARE_POINT = r"\s*,?\s*(?:point\s*)?[a-z]{1,4}"
_OF = r"\s*,?\s*(?:(?:du|de\s+la|de|of\s+the|of)\s+|de\s+l['’]\s*)?"
_CODE_FIRST = (
    _CODE.format(name="code")
    + r"\s*,?\s*"
    + _ART.format(name="article")
    + rf"(?:{_PARA.format(name='paragraph')}(?:{_POINT}{{1,2}}|{_BARE_POINT})?)?"
)
# With the code last, a bare point letter would be read as the code, so only "(c)" points.
_ARTICLE_FIRST = (
    _ART.format(name="r_article")
    + rf"(?:{_PARA.format(name='r_paragraph')}{_POINT}{{0,2}})?"
    + _OF
    + _CODE.format(name="r_code")
)
LABEL_RE = re.compile(
    rf"(?P<space>[ \t]*)\[\s*(?:{_CODE_FIRST}|{_ARTICLE_FIRST})\s*\]", re.IGNORECASE
)

# Spellings a model uses for the regulations of the corpus, after upper-casing and
# dropping spaces and hyphens. Anything else keeps its own normalized code.
ALIASES: dict[str, str] = {
    "DORA": "DORA",
    "AIACT": "AIACT",
    "EUAIACT": "AIACT",
    "RIA": "AIACT",
    "RGPD": "RGPD",
    "GDPR": "RGPD",
    "AMLR": "AMLR",
    "LCBFT": "AMLR",
}

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


def normalize_code(code: str) -> str:
    key = re.sub(r"[\s-]+", "", code).upper()
    return ALIASES.get(key, key)


def _parse(match: re.Match[str]) -> RawCitation:
    if match["code"] is not None:
        return RawCitation(
            regulation=normalize_code(match["code"]),
            article=match["article"].lower(),
            paragraph=match["paragraph"].lower() if match["paragraph"] else None,
        )
    return RawCitation(
        regulation=normalize_code(match["r_code"]),
        article=match["r_article"].lower(),
        paragraph=match["r_paragraph"].lower() if match["r_paragraph"] else None,
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
