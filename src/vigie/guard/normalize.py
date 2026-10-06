"""Clean a question before any guard sees it.

Attacks hide in the gap between what a person reads and what a pattern matches: a zero
width space inside "ignore", a right-to-left override that flips the displayed text,
fullwidth letters, or the whole instruction sent as base64. Normalizing first means every
detector downstream judges the same text, and the pipeline answers that same text too.
"""

from __future__ import annotations

import base64
import binascii
import html
import re
import unicodedata
from dataclasses import dataclass, field
from urllib.parse import unquote

# Format characters (category Cf) are invisible by definition: zero width spaces and
# joiners, bidi embeddings and overrides, the byte order mark, soft hyphens, and the tag
# block used to smuggle ASCII. None of them has a place in a compliance question.
_TAG_BLOCK = range(0xE0000, 0xE0080)

# Long runs of the base64 alphabet. Short ones are ordinary words or references.
_BASE64_RUN = re.compile(r"[A-Za-z0-9+/_-]{16,}={0,2}")
_PERCENT = re.compile(r"(?:%[0-9A-Fa-f]{2}){3,}")
_ENTITY = re.compile(r"&(?:#\d{2,7}|#x[0-9A-Fa-f]{2,6}|[A-Za-z]{2,8});")
_SPACES = re.compile(r"[ \t]+")

# A decoded run counts only if it reads like text; random identifiers decode to noise.
_MIN_PRINTABLE_SHARE = 0.9


@dataclass(frozen=True)
class NormalizedInput:
    # What the pipeline answers: NFKC, invisible characters removed, spaces collapsed.
    text: str
    # Every hidden payload found in the text, decoded and cleaned the same way.
    decoded: tuple[str, ...] = field(default_factory=tuple)

    @property
    def guard_view(self) -> str:
        """What the guards read: the text, then each decoded payload on its own line."""
        return "\n".join((self.text, *self.decoded))


def _is_invisible(char: str) -> bool:
    return unicodedata.category(char) == "Cf" or ord(char) in _TAG_BLOCK


def clean(text: str) -> str:
    folded = unicodedata.normalize("NFKC", text)
    visible = "".join(ch for ch in folded if not _is_invisible(ch))
    lines = (_SPACES.sub(" ", line).strip() for line in visible.splitlines())
    return "\n".join(line for line in lines if line)


def _readable(candidate: str) -> bool:
    if not candidate.strip():
        return False
    printable = sum(ch.isprintable() or ch.isspace() for ch in candidate)
    return printable / len(candidate) >= _MIN_PRINTABLE_SHARE and any(
        ch.isalpha() for ch in candidate
    )


def _decode_base64(run: str) -> str | None:
    standard = run.replace("-", "+").replace("_", "/")
    padded = standard + "=" * (-len(standard) % 4)
    try:
        decoded = base64.b64decode(padded, validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return None
    return decoded if _readable(decoded) else None


def decode_hidden(text: str) -> tuple[str, ...]:
    """Return the payloads hidden in base64, percent-encoding or HTML entities."""
    found: list[str] = []
    for match in _BASE64_RUN.finditer(text):
        decoded = _decode_base64(match.group())
        if decoded is not None:
            found.append(decoded)
    if _PERCENT.search(text):
        found.append(unquote(text))
    if _ENTITY.search(text):
        found.append(html.unescape(text))
    # A payload is cleaned only once decoded: invisible characters may sit inside it,
    # and a decoded text is held to the same rules as the visible one.
    cleaned = (clean(item) for item in found)
    return tuple(dict.fromkeys(item for item in cleaned if item and item != text))


def normalize(text: str) -> NormalizedInput:
    cleaned = clean(text)
    return NormalizedInput(text=cleaned, decoded=decode_hidden(cleaned))
