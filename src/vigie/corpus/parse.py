"""Cut an Official Journal XHTML into citable chunks.

The Cellar XHTML carries ELI anchors: `art_28` for an article, `028.001` for its first
paragraph, `cpt_III` for a chapter, `anx_II` for an annex, `rct_12` for a recital. We lean
on those ids rather than on the visible headings, which change wording between texts.
"""

from __future__ import annotations

import re
import warnings

from bs4 import BeautifulSoup, Tag, XMLParsedAsHTMLWarning

from vigie.config import Settings
from vigie.corpus.models import Chunk, ChunkKind
from vigie.corpus.render import css_classes, normalize, render, strip_note_calls, word_count
from vigie.corpus.sources import Regulation, eurlex_url

_ARTICLE_ID = re.compile(r"^art_\w+$")
_PARAGRAPH_ID = re.compile(r"^\d{3}\.(\d{3})$")
_CHAPTER_ID = re.compile(r"^cpt_[^.]+$")
_ANNEX_ID = re.compile(r"^anx_[^.]+$")
_RECITAL_ID = re.compile(r"^rct_\d+$")
_WHITESPACE = re.compile(r"\s+")


def clean_id(raw_id: str) -> str:
    """AMLR writes its annex ids as "anx_<no-break space>I"; citations need "anx_I"."""
    return _WHITESPACE.sub("", raw_id)


class _Context:
    """What every chunk of one regulation shares, so helpers take one argument, not six."""

    def __init__(self, regulation: Regulation, settings: Settings, retrieved_on: str) -> None:
        self.regulation = regulation
        self.settings = settings
        self.retrieved_on = retrieved_on
        self.chapters: dict[str, str] = {}

    def chunk(
        self,
        kind: ChunkKind,
        raw_id: str,
        lines: list[str],
        *,
        paragraph: str | None = None,
        suffix: str = "",
        title: str = "",
        chapter: str = "",
    ) -> Chunk:
        anchor = clean_id(raw_id)
        return Chunk(
            regulation=self.regulation.code,
            celex=self.regulation.celex,
            kind=kind,
            article=anchor.split("_", 1)[1],
            paragraph=paragraph,
            title=title,
            chapter=chapter,
            text="\n".join(lines),
            # The link keeps the id exactly as EUR-Lex prints it, otherwise the anchor misses.
            url=eurlex_url(self.regulation, self.settings, raw_id),
            eid=anchor + suffix,
            retrieved_on=self.retrieved_on,
        )


def parse_regulation(
    xhtml: bytes,
    regulation: Regulation,
    settings: Settings,
    *,
    retrieved_on: str,
    include_recitals: bool = False,
) -> list[Chunk]:
    with warnings.catch_warnings():
        # The document is XHTML; the lenient HTML parser copes with it better than the XML
        # one would with the odd entity, and bs4 only warns about the choice.
        warnings.simplefilter("ignore", XMLParsedAsHTMLWarning)
        soup = BeautifulSoup(xhtml, "lxml")
    strip_note_calls(soup)
    context = _Context(regulation, settings, retrieved_on)
    chunks: list[Chunk] = []
    if include_recitals:
        for div in soup.find_all("div", id=_RECITAL_ID):
            chunks.append(context.chunk("recital", str(div["id"]), render(div)))
    for div in soup.find_all("div", id=_ARTICLE_ID):
        chunks.extend(_article(div, context))
    for div in soup.find_all("div", id=_ANNEX_ID):
        chunks.extend(_annex(div, context))
    return chunks


def article_numbers(chunks: list[Chunk]) -> list[str]:
    """Distinct article numbers, in reading order, whatever the splitting did."""
    return list(dict.fromkeys(c.article for c in chunks if c.kind == "article"))


def _article(div: Tag, context: _Context) -> list[Chunk]:
    raw_id = str(div["id"])
    title_el = div.find("div", class_="eli-title", recursive=False)
    title = normalize(title_el.get_text(" ")) if title_el else ""
    chapter = _chapter_of(div, context)
    intro: list[str] = []
    paragraphs: list[tuple[str, list[str]]] = []
    for child in div.find_all(True, recursive=False):
        classes = css_classes(child)
        if "oj-ti-art" in classes or "eli-title" in classes:
            continue
        match = _PARAGRAPH_ID.match(str(child.get("id", "")))
        if child.name == "div" and match:
            paragraphs.append((str(int(match.group(1))), render(child)))
        elif paragraphs:
            paragraphs[-1][1].extend(render(child))
        else:
            intro.extend(render(child))

    limit = context.settings.corpus_split_words
    every_line = intro + [line for _, lines in paragraphs for line in lines]
    sections: list[tuple[str | None, str, list[str]]] = [(None, "", every_line)]
    if paragraphs and word_count(every_line) > limit:
        # A short preamble before paragraph 1 only makes sense read with it.
        paragraphs[0] = (paragraphs[0][0], intro + paragraphs[0][1])
        sections = [(number, f".par_{number}", lines) for number, lines in paragraphs]

    chunks: list[Chunk] = []
    for paragraph, suffix, lines in sections:
        # Some paragraphs are lists of definitions thousands of words long (AMLR art. 2 §1):
        # they are packed into parts so no chunk blows past the embedding window.
        parts = _group(lines, limit)
        for index, part in enumerate(parts, start=1):
            part_suffix = f"{suffix}.part_{index}" if len(parts) > 1 else suffix
            chunks.append(
                context.chunk(
                    "article",
                    raw_id,
                    part,
                    paragraph=paragraph,
                    suffix=part_suffix,
                    title=title,
                    chapter=chapter,
                )
            )
    return chunks


def _annex(div: Tag, context: _Context) -> list[Chunk]:
    raw_id = str(div["id"])
    headings: list[str] = []
    lines: list[str] = []
    for child in div.find_all(True, recursive=False):
        # The annex opens with "ANNEXE III" then its title, both styled as document titles.
        if not lines and "oj-doc-ti" in css_classes(child):
            headings.append(normalize(child.get_text(" ")))
        else:
            lines.extend(render(child))
    title = " ".join(headings[1:])
    parts = _group(lines, context.settings.corpus_split_words)
    return [
        context.chunk(
            "annex", raw_id, part, suffix=f".part_{i}" if len(parts) > 1 else "", title=title
        )
        for i, part in enumerate(parts, start=1)
    ]


def _chapter_of(div: Tag, context: _Context) -> str:
    parent = div.find_parent("div", id=_CHAPTER_ID)
    if parent is None:
        return ""
    key = str(parent["id"])
    if key not in context.chapters:
        heading = parent.find("p", recursive=False)
        title = parent.find("div", class_="eli-title", recursive=False)
        pieces = [normalize(el.get_text(" ")) for el in (heading, title) if el is not None]
        context.chapters[key] = " - ".join(piece for piece in pieces if piece)
    return context.chapters[key]


def _group(lines: list[str], limit: int) -> list[list[str]]:
    """Pack consecutive lines into parts of at most `limit` words, never splitting a line."""
    parts: list[list[str]] = [[]]
    count = 0
    for line in lines:
        words = len(line.split())
        if parts[-1] and count + words > limit:
            parts.append([])
            count = 0
        parts[-1].append(line)
        count += words
    return parts
