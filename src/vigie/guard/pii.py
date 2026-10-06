"""Find and mask the personal data that is easy to recognize: e-mails, IBANs, phone
numbers and payment cards.

The audit log is the only place where question text is kept, so whatever a user pastes
by mistake is masked before the line is written. Model answers go through the same mask
on the way out. Names and postal addresses are out of reach of patterns; they stay a
residual risk written in the threat model.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
# Two letters, two check digits, then groups of four, with or without spaces.
_IBAN = re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){3,7}(?: ?[A-Z0-9]{1,3})?\b", re.IGNORECASE)
_CARD = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")
# French numbers, national or international, with the usual separators.
_PHONE = re.compile(r"(?<![\d+])(?:\+33 ?(?:\(0\) ?)?|0)[1-9](?:[ .-]?\d{2}){4}(?!\d)")

# Order matters: a card number holds digit runs that the phone pattern would also take.
_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("email", _EMAIL),
    ("iban", _IBAN),
    ("card", _CARD),
    ("phone", _PHONE),
)
MASKS = {"email": "[EMAIL]", "iban": "[IBAN]", "card": "[CARTE]", "phone": "[TÉLÉPHONE]"}


@dataclass(frozen=True)
class MaskResult:
    text: str
    kinds: tuple[str, ...]


def luhn_valid(digits: str) -> bool:
    """Payment card checksum; it keeps long reference numbers from being masked."""
    total = 0
    for index, char in enumerate(reversed(digits)):
        value = int(char)
        if index % 2 == 1:
            value = value * 2 - 9 if value > 4 else value * 2
        total += value
    return total % 10 == 0


def mask_pii(text: str) -> MaskResult:
    kinds: list[str] = []
    masked = text
    for kind, pattern in _PATTERNS:

        def replace(match: re.Match[str], kind: str = kind) -> str:
            if kind == "card" and not luhn_valid(re.sub(r"\D", "", match.group())):
                return match.group()
            kinds.append(kind)
            return MASKS[kind]

        masked = pattern.sub(replace, masked)
    return MaskResult(masked, tuple(dict.fromkeys(kinds)))
