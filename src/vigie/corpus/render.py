"""Turn Official Journal XHTML fragments into plain text lines.

The Official Journal lays out enumerations as two-column tables ("a)" on the left, the
content on the right), nested as deep as the law goes. Flattening them naively glues the
label to the previous sentence, so lists are rebuilt here as "a) ..." lines.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

from bs4 import Tag
from bs4.element import NavigableString

# Python's \s already covers the no-break spaces (U+00A0, U+202F, U+2009) the Official
# Journal sprinkles everywhere; zero-width spaces are not whitespace, so they go separately.
_SPACES = re.compile(r"\s+")
_INVISIBLE = re.compile("[​‌‍⁠﻿]")
_EMPTY_NOTE_CALL = re.compile(r"\s*\(\s*\)")
# A list label is short ("a)", "iii)", "12.", "-"); anything longer is a real table cell.
_MAX_LABEL_CHARS = 10


def normalize(text: str) -> str:
    text = _INVISIBLE.sub("", text)
    return _SPACES.sub(" ", text).strip()


def strip_note_calls(root: Tag) -> None:
    """Drop footnote call marks, which would otherwise read as stray numbers in the text."""
    for tag in root.select("span.oj-note-tag"):
        target = tag.parent if isinstance(tag.parent, Tag) and tag.parent.name == "a" else tag
        target.decompose()


def render(element: Tag) -> list[str]:
    """Lines of text for one block element."""
    if element.name == "table":
        return _render_table(element)
    if element.name == "div":
        return render_children(element)
    text = _clean(element.get_text(""))
    return [text] if text else []


def render_children(element: Tag) -> list[str]:
    lines: list[str] = []
    for child in element.children:
        if isinstance(child, Tag):
            lines.extend(render(child))
        # Comments are NavigableString subclasses; an exact type check keeps them out.
        elif type(child) is NavigableString:
            text = _clean(str(child))
            if text:
                lines.append(text)
    return lines


def css_classes(element: Tag) -> list[str]:
    value = element.get("class")
    if isinstance(value, str):
        return value.split()
    return list(value or [])


def word_count(lines: list[str]) -> int:
    return sum(len(line.split()) for line in lines)


def _clean(text: str) -> str:
    return normalize(_EMPTY_NOTE_CALL.sub("", text))


def _rows(table: Tag) -> Iterator[Tag]:
    for child in table.children:
        if not isinstance(child, Tag):
            continue
        if child.name == "tr":
            yield child
        elif child.name in {"tbody", "thead", "tfoot"}:
            yield from (row for row in child.children if isinstance(row, Tag) and row.name == "tr")


def _render_table(table: Tag) -> list[str]:
    lines: list[str] = []
    for row in _rows(table):
        cells = [
            cell for cell in row.children if isinstance(cell, Tag) and cell.name in {"td", "th"}
        ]
        if len(cells) == 2:
            label = _clean(cells[0].get_text(""))
            body = render_children(cells[1])
            if len(label) <= _MAX_LABEL_CHARS and body:
                lines.append(f"{label} {body[0]}".strip())
                lines.extend(body[1:])
                continue
        texts = [" ".join(render_children(cell)) for cell in cells]
        row_text = " | ".join(text for text in texts if text)
        if row_text:
            lines.append(row_text)
    return lines
