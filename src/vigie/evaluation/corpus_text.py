"""Article texts the golden set is checked against, read from chunks or from Cellar XHTML.

Two sources are accepted on purpose. The chunk JSONL written by the ingestion step is what
production indexes, so it is the reference once it exists. The raw XHTML cached from Cellar
lets the dataset be checked before ingestion is merged, and gives a second, independent
reading of the official text when the two need to be compared.
"""

from __future__ import annotations

import json
import re
import warnings
from collections.abc import Iterable, Mapping
from pathlib import Path

from bs4 import BeautifulSoup, Tag, XMLParsedAsHTMLWarning

from vigie.evaluation.regulations import CELEX_REGULATION, REGULATION_CELEX, article_id

# Cellar uses non-breaking and narrow non-breaking spaces around punctuation. Python's \s
# already matches both, so one pattern folds every kind of blank into a single space.
_BLANKS = re.compile(r"\s+")
_ARTICLE_DIV = re.compile(r"^art_(\d+[a-z]*)$")


def normalize_space(text: str) -> str:
    """Collapse every run of whitespace, non-breaking ones included, into one space."""
    return _BLANKS.sub(" ", text).strip()


def load_chunks_dir(directory: Path) -> dict[str, str]:
    """Read every ``*.jsonl`` chunk file and join the chunks of each article.

    A long article is split into several chunks by paragraph; joining them back gives the
    whole article, so a reference quote is found whichever chunk carries it.
    """
    parts: dict[str, list[str]] = {}
    files = sorted(directory.glob("*.jsonl"))
    if not files:
        raise FileNotFoundError(f"no chunk JSONL file in {directory}")
    for path in files:
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                chunk = json.loads(line)
                key = article_id(str(chunk["regulation"]), str(chunk["article"]))
                text = str(chunk["text"])
            except (json.JSONDecodeError, KeyError) as exc:
                raise ValueError(f"{path.name}:{line_number}: unreadable chunk ({exc})") from exc
            parts.setdefault(key, []).append(text)
    return {key: normalize_space(" ".join(texts)) for key, texts in parts.items()}


def _block_texts(article: Tag) -> Iterable[str]:
    # Only paragraphs carry text in the Official Journal markup. Reading them one by one,
    # rather than the whole div, keeps the point letter of a list ("a)") and its sentence
    # apart, which is also how the ingestion step reads them.
    for paragraph in article.find_all("p"):
        yield paragraph.get_text("")


def parse_xhtml_articles(regulation: str, xhtml: str) -> dict[str, str]:
    """Extract the normalized text of every article of one Cellar XHTML document."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", XMLParsedAsHTMLWarning)
        soup = BeautifulSoup(xhtml, "lxml")
    articles: dict[str, str] = {}
    for div in soup.find_all("div", id=_ARTICLE_DIV):
        match = _ARTICLE_DIV.match(str(div["id"]))
        if match is None:  # pragma: no cover - find_all already filtered on this pattern
            continue
        text = normalize_space(" ".join(_block_texts(div)))
        articles[article_id(regulation, match.group(1))] = text
    return articles


def load_xhtml_dir(directory: Path) -> dict[str, str]:
    """Read the cached Cellar documents, one file per CELEX number (``32022R2554.xhtml``)."""
    articles: dict[str, str] = {}
    for path in sorted(directory.glob("*.xhtml")):
        regulation = CELEX_REGULATION.get(path.stem)
        if regulation is None:
            continue
        articles.update(parse_xhtml_articles(regulation, path.read_text(encoding="utf-8")))
    if not articles:
        expected = ", ".join(f"{celex}.xhtml" for celex in REGULATION_CELEX.values())
        raise FileNotFoundError(f"no regulation XHTML in {directory}, expected {expected}")
    return articles


def load_corpus(directory: Path) -> Mapping[str, str]:
    """Pick the right reader for a directory: chunk JSONL first, cached XHTML otherwise."""
    if any(directory.glob("*.jsonl")):
        return load_chunks_dir(directory)
    return load_xhtml_dir(directory)
